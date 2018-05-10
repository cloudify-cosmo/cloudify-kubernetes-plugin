import copy

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError

DEFINITION_KEY_SPEC = 'spec'
DEFINITION_KEY_NODE_SELECTOR = 'nodeSelector'
DEFINITION_KEY_TEMPLATE = 'template'
PROPERTY_DEFINITION = 'definition'
PROPERTY_PARAM_NAME = 'param_name'
PROPERTY_PARAMS = 'params'
PROPERTY_OLD_PARAMS = 'old_params'
RUNTIME_PROPERTY_RESULT = 'result'
RUNTIME_PROPERTY_RESULT_CURRENT = 'current'
RUNTIME_PROPERTY_RESULT_OLD = 'old'


def _get_definition():
    definition = ctx.node.properties.get(PROPERTY_DEFINITION, None)

    if not definition:
        raise NonRecoverableError('"Definition" property is not defined')

    return definition


def _get_label():
    label_property_name = ctx.node.properties.get(PROPERTY_PARAM_NAME, '')
    params = ctx.instance.runtime_properties.get(PROPERTY_PARAMS, {})

    return (
        params.get(label_property_name, None),
        params.get(PROPERTY_OLD_PARAMS, {}).get(label_property_name, None)
    )


def _render(definition, label):
    rendered_definition = copy.deepcopy(definition)

    if label:
        rendered_definition[
            DEFINITION_KEY_SPEC
        ][
            DEFINITION_KEY_TEMPLATE
        ][
            DEFINITION_KEY_SPEC
        ][
            DEFINITION_KEY_NODE_SELECTOR
        ] = label

    return rendered_definition


def render():
    ctx.logger.info('Rendering Kubernetes resource template ...')

    definition = _get_definition()
    ctx.logger.info('Got template: \n{0}'.format(definition))

    label, old_label = _get_label()
    ctx.logger.info(
        'Got Kubernetes label(s) - current: {0}, (old: {1})'
        .format(label, old_label)
    )

    result = {
        RUNTIME_PROPERTY_RESULT_CURRENT: _render(definition, label),
        RUNTIME_PROPERTY_RESULT_OLD: _render(definition, old_label)
    }
    ctx.logger.info('Rendered templates: {0}'.format(result))

    ctx.instance.runtime_properties[RUNTIME_PROPERTY_RESULT] = result
    ctx.logger.info('Done')


render()
