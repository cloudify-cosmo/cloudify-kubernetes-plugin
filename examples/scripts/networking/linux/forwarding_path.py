from fabric.api import sudo, settings
from cloudify import ctx
from cloudify.exceptions import RecoverableError, NonRecoverableError


def _get_input_parameter(name, kwargs):
    parameter = ctx.node.properties.get(name, kwargs.get(name, None))

    if not parameter:
        raise NonRecoverableError(
            'Mandatory input parameter {0} for lifecycle script not specified'
            .format(name)
        )

    return parameter


def _get_container_pid(pod_name):
    command = "kubectl describe pod %s | grep 'Container ID' | " \
              "awk '{print $3}' | cut -c 10- | " \
              "xargs -I _ docker inspect --format '{{ .State.Pid }}' _"\
              % pod_name

    ctx.logger.info('Geting PID for container in pod {0}'.format(pod_name))
    ctx.logger.info('Executing command: {0}'.format(command))
    pid = sudo(command)

    if not pid:
        raise RecoverableError(
            'Cannot get PID of container in pod {0}. '
            'Waiting for pod to be in Running state.'
            .format(pod_name)
        )

    ctx.logger.info('PID: {0}'.format(pid))
    return pid


def _check_if_route_exists(pid, network):
    ctx.logger.info(
        'Checking if route to network {0} already exists in namespace {1}'
        .format(network, pid)
    )

    command = 'nsenter -t {0} -n ip route | grep "{1}"'.format(pid, network)
    ctx.logger.info('Executing command: {0}'.format(command))

    with settings(warn_only=True):
        return sudo(command).return_code == 0


def _configure_routing(operation, members):
    ctx.logger.info(
        'Preparing route config for {0} operation ...'.format(operation)
    )

    for member in members:
        route_config = None

        pid = _get_container_pid(member['name'])
        ctx.logger.info(
            'Route will be configured in network namespace: {0}'.format(pid)
        )

        if _check_if_route_exists(pid, member['network']):
            ctx.logger.info('Route already exists. Overriding.')
            operation = 'replace'

        if 'next_hop' in member:
            route_config = 'ip route {0} {1} via {2}'\
                .format(operation, member['network'], member['next_hop'])
        elif 'interface' in member:
            route_config = 'ip route {0} {1} dev {2}'\
                .format(operation, member['network'], member['interface'])
        else:
            ctx.logger.warn(
                'Invalid FP member - cannot prepare route config for {0}'
                .format(member)
            )
            continue

        ctx.logger.info(
            'Route config to be executed on container: {0}'
            .format(route_config)
        )

        command = 'nsenter -t {0} -n {1}'.format(pid, route_config)
        ctx.logger.info(
            'Executing final command to configure route {0}'.format(command)
        )

        sudo(command)


def create(**kwargs):
    _configure_routing(
        'add',
        members=_get_input_parameter('members', kwargs)
    )


def delete(**kwargs):
    _configure_routing(
        'delete',
        members=_get_input_parameter('members', kwargs)
    )
