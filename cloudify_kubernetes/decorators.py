# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from cloudify import ctx
from cloudify.exceptions import (
    OperationRetry,
    RecoverableError,
    NonRecoverableError
)
from cloudify.decorators import operation

from .utils import (generate_traceback_exception,
                    retrieve_path,
                    get_node,
                    get_instance,
                    NODE_PROPERTY_FILE,
                    NODE_PROPERTY_FILE_RESOURCE_PATH)
from .k8s import (CloudifyKubernetesClient,
                  KubernetesApiAuthenticationVariants,
                  KubernetesApiConfigurationVariants,
                  KuberentesApiInitializationFailedError,
                  KuberentesInvalidPayloadClassError,
                  KuberentesInvalidApiClassError,
                  KuberentesInvalidApiMethodError,
                  KuberentesMappingNotFoundError)

NODE_PROPERTY_AUTHENTICATION = 'authentication'
NODE_PROPERTY_CONFIGURATION = 'configuration'
RELATIONSHIP_TYPE_MANAGED_BY_MASTER = (
    'cloudify.kubernetes.relationships.managed_by_master'
)
INSTANCE_RUNTIME_PROPERTY_KUBERNETES = 'kubernetes'


def _retrieve_master(resource_instance):
    for relationship in resource_instance.relationships:
        if relationship.type == RELATIONSHIP_TYPE_MANAGED_BY_MASTER:
            return relationship.target


def _retrieve_property(_ctx, property_name):
    property_from_client_config = get_node(_ctx).properties \
        .get('client_config', {}).get(property_name, {})
    target = _retrieve_master(get_instance(_ctx))

    if target:
        _ctx.logger.info("using property from managed_by_master"
                         " relationship for node: {0}, it will be deprecated"
                         " soon please use client_config property!"
                         .format(_ctx.node.name))
        configuration = target.node.properties.get(property_name, {})
        configuration.update(
            target.instance.runtime_properties.get(property_name, {})
        )

    else:
        configuration = property_from_client_config
        configuration.update(
            get_instance(_ctx).runtime_properties.get(property_name, {}))

    return configuration


def _multidefinition_resource_task(task, definitions, kwargs,
                                   retrieve_mapping, use_existing=False,
                                   cleanup_runtime_properties=False):
    curr_num = 0
    # we have several definitions (not one!)
    multicalls = len(definitions) > 1
    # we can have several resources in one file, save origin
    origin_path = None
    if NODE_PROPERTY_FILE in kwargs and multicalls:
        # save original path only in case multicalls
        origin_path = kwargs[
            NODE_PROPERTY_FILE].get(NODE_PROPERTY_FILE_RESOURCE_PATH)
    elif NODE_PROPERTY_FILE in ctx.node.properties and multicalls:
        # copy origin file name to kwargs
        kwargs[NODE_PROPERTY_FILE] = ctx.node.properties[NODE_PROPERTY_FILE]
        # save origin path
        origin_path = kwargs[
            NODE_PROPERTY_FILE].get(NODE_PROPERTY_FILE_RESOURCE_PATH)
    # iterate by definitions list
    for definition in definitions:
        kwargs['resource_definition'] = definition
        if retrieve_mapping:
            kwargs['api_mapping'] = retrieve_mapping(**kwargs)
        # we can have several resources in one file
        if origin_path:
            kwargs[NODE_PROPERTY_FILE][NODE_PROPERTY_FILE_RESOURCE_PATH] = (
                "{name}#{curr_num}".format(
                    name=origin_path,
                    curr_num=str(curr_num)
                ))
            curr_num += 1
        # check current state
        path = retrieve_path(kwargs)
        if path:
            current_state = ctx.instance.runtime_properties.get(
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES, {}).get(path)
        else:
            current_state = ctx.instance.runtime_properties.get(
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES)
        # ignore prexisted state
        if not use_existing and current_state:
            ctx.logger.info("Ignore existing object state")
            continue
        # ignore if we dont have any object yet
        if use_existing and not current_state:
            ctx.logger.info("Ignore unexisted object state")
            continue
        # finally run
        task(**kwargs)
        # cleanup after successful run
        if current_state and cleanup_runtime_properties:
            if path:
                del ctx.instance.runtime_properties[
                    INSTANCE_RUNTIME_PROPERTY_KUBERNETES][path]
            else:
                ctx.instance.runtime_properties[
                    INSTANCE_RUNTIME_PROPERTY_KUBERNETES] = {}
            # remove empty kubernetes property
            if not ctx.instance.runtime_properties[
                INSTANCE_RUNTIME_PROPERTY_KUBERNETES
            ]:
                del ctx.instance.runtime_properties[
                    INSTANCE_RUNTIME_PROPERTY_KUBERNETES]
            # force save
            ctx.instance.runtime_properties.dirty = True
            ctx.instance.update()


def resource_task(retrieve_resource_definition=None,
                  retrieve_resources_definitions=None,
                  retrieve_mapping=None, use_existing=False,
                  cleanup_runtime_properties=False):
    def decorator(task, **kwargs):
        def wrapper(**kwargs):
            try:
                definitions = []
                # use single definition source
                if retrieve_resource_definition:
                    definitions = [retrieve_resource_definition(**kwargs)]
                # use multi definition source
                elif retrieve_resources_definitions:
                    definitions = retrieve_resources_definitions(**kwargs)
                # apply definition
                _multidefinition_resource_task(
                    task, definitions, kwargs, retrieve_mapping,
                    use_existing=use_existing,
                    cleanup_runtime_properties=cleanup_runtime_properties)
            except (KuberentesMappingNotFoundError,
                    KuberentesInvalidPayloadClassError,
                    KuberentesInvalidApiClassError,
                    KuberentesInvalidApiMethodError) as e:
                raise NonRecoverableError(str(e))
            except OperationRetry as e:
                error_traceback = generate_traceback_exception()
                ctx.logger.error(
                    'Error traceback {0} with message {1}'.format(
                        error_traceback['traceback'], error_traceback[
                            'message']))
                raise OperationRetry(
                    '{0}'.format(str(e)),
                    retry_after=15,
                    causes=[error_traceback]
                )
            except NonRecoverableError as e:
                error_traceback = generate_traceback_exception()
                ctx.logger.error(
                    'Error traceback {0} with message {1}'.format(
                        error_traceback['traceback'], error_traceback[
                            'message']))
                raise NonRecoverableError(
                    '{0}'.format(str(e)),
                    causes=[error_traceback]
                )
            except Exception as e:
                error_traceback = generate_traceback_exception()
                ctx.logger.error(
                    'Error traceback {0} with message {1}'.format(
                        error_traceback['traceback'], error_traceback[
                            'message']))
                raise RecoverableError(
                    '{0}'.format(str(e)),
                    causes=[error_traceback]
                )

        return wrapper

    return decorator


def with_kubernetes_client(function):
    def wrapper(**kwargs):
        configuration_property = _retrieve_property(
            ctx,
            NODE_PROPERTY_CONFIGURATION
        )

        authentication_property = _retrieve_property(
            ctx,
            NODE_PROPERTY_AUTHENTICATION
        )

        try:
            kwargs['client'] = CloudifyKubernetesClient(
                ctx.logger,
                KubernetesApiConfigurationVariants(
                    ctx.logger,
                    configuration_property,
                    download_resource=ctx.download_resource
                ),
                KubernetesApiAuthenticationVariants(
                    ctx.logger,
                    authentication_property
                )
            )

            function(**kwargs)
        except KuberentesApiInitializationFailedError as e:
            error_traceback = generate_traceback_exception()
            ctx.logger.error(
                'Error traceback {0} with message {1}'.format(
                    error_traceback['traceback'], error_traceback[
                        'message']))
            raise RecoverableError(
                '{0}'.format(str(e)),
                causes=[error_traceback]
            )
        except OperationRetry as e:
            error_traceback = generate_traceback_exception()
            ctx.logger.error(
                'Error traceback {0} with message {1}'.format(
                    error_traceback['traceback'], error_traceback[
                        'message']))
            raise OperationRetry(
                '{0}'.format(str(e)),
                retry_after=15,
                causes=[error_traceback]
            )
        except NonRecoverableError as e:
            error_traceback = generate_traceback_exception()
            ctx.logger.error(
                'Error traceback {0} with message {1}'.format(
                    error_traceback['traceback'], error_traceback[
                        'message']))
            raise NonRecoverableError(
                '{0}'.format(str(e)),
                causes=[error_traceback]
            )
        except Exception as e:
            error_traceback = generate_traceback_exception()
            ctx.logger.error(
                'Error traceback {0} with message {1}'.format(
                    error_traceback['traceback'], error_traceback[
                        'message']))
            raise RecoverableError(
                '{0}'.format(str(e)),
                causes=[error_traceback]
            )

    return operation(func=wrapper, resumable=True)
