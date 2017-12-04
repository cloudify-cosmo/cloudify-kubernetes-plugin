from fabric.api import sudo
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError


def _get_input_parameter(name, kwargs):
    parameter = ctx.node.properties.get(name, kwargs.get(name, None))

    if not parameter:
        raise NonRecoverableError(
            'Mandatory input parameter {0} for lifecycle script not specified'
            .format(name)
        )

    return parameter


def _add_bridge(name):
    ctx.logger.info('Adding bridge ...')

    command = 'brctl addbr {0}'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _configure_interfaces(name, input_interface_name, output_interface_name):
    ctx.logger.info('Adding interfaces to bridge ...')

    command = 'brctl addif {0} {1} {2}'\
        .format(name, input_interface_name, output_interface_name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _configure_ip(name, ip):
    ctx.logger.info('Configuring gateway IP address ...')

    command = 'ifconfig {0} {1} netmask 255.255.255.0 up'.format(name, ip)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _delete_bridge(name):
    command = 'ifconfig {0} down'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)

    command = 'brctl delbr {0}'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _create(name, ip, input_interface, output_interface):
    ctx.logger.info(
        'Configuring VL with parameters: name={0}, ip={1}, '
        'input_interface={2}, output_interface={3}'
        .format(name, ip, input_interface, output_interface)
    )

    _add_bridge(name)
    _configure_interfaces(name, input_interface, output_interface)
    _configure_ip(name, ip)


def _delete(name):
    ctx.logger.info('Deleting VL {0}'.format(name))

    _delete_bridge(name)


def create(**kwargs):
    _create(
        name=_get_input_parameter('name', kwargs),
        ip=_get_input_parameter('ip', kwargs),
        input_interface=_get_input_parameter('input_interface', kwargs),
        output_interface=_get_input_parameter('output_interface', kwargs)
    )


def delete(**kwargs):
    _delete(name=_get_input_parameter('name', kwargs))
