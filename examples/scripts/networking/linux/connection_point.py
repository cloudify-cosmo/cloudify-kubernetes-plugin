from fabric.api import settings, sudo
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
    get_pid_command = "kubectl describe pod %s | grep 'Container ID' | " \
                      "awk '{print $3}' |  cut -c 10- | xargs " \
                      "-I _ docker inspect --format '{{ .State.Pid }}' _"\
                      % pod_name

    ctx.logger.info('Geting PID for container in pod {0}'.format(pod_name))
    ctx.logger.info('Executing command: {0}'.format(get_pid_command))
    pid = sudo(get_pid_command)

    if not pid:
        raise RecoverableError(
            'Cannot get PID of container in pod {0}. '
            'Waiting for pod to be in Running state.'
            .format(pod_name)
        )

    ctx.logger.info('PID: {0}'.format(pid))
    return pid


def _check_if_interface_exists(pid, name):
    prefix = ''

    if pid:
        ctx.logger.info(
            'Checking if interface {0} exists in network namespace {1}'
            .format(name, pid)
        )
        prefix = 'nsenter -t {0} -n '.format(pid)
    else:
        ctx.logger.info(
            'Checking if interface {0} exists in host system'
            .format(name)
        )

    command = '{0}ifconfig {1}'.format(prefix, name)
    ctx.logger.info('Executing command: {0}'.format(command))

    with settings(warn_only=True):
        return sudo(command).return_code == 0


def _create_interfaces_pair(out_name, in_name):
    ctx.logger.info(
        'Creating veth interfaces pair - '
        'external interface: {0}, internal interface: {1}'
        .format(out_name, in_name)
    )

    command = 'ip link add {0} type veth peer name {1}'\
        .format(out_name, in_name)
    ctx.logger.info('Executing command: {0}'.format(command))

    sudo(command)


def _configure_internal_interface(pid, name, ip):
    ctx.logger.info(
        'Configuring external interface: {0}, netns: {1}'
        .format(name, pid)
    )

    command = 'ip link set netns {0} {1}'.format(pid, name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)

    _configure_existing_interface(pid, name, ip, False)


def _configure_external_interface(name):
    ctx.logger.info('Configuring external interface: {0}'.format(name))

    command = 'ifconfig {0} up'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _configure_existing_interface(pid, name, ip, down):
    ip_config = '{0} netmask 255.255.255.0 '.format(ip) if ip else ' '
    state_config = 'down' if down else 'up'
    command = 'nsenter -t {0} -n ifconfig {1} {2}{3}'\
        .format(pid, name, ip_config, state_config)

    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _move_host_interface_to_namespace(pid, name):
    ctx.logger.info(
        'Moving interface {0} to network namespace {1}'
        .format(name, pid)
    )

    command = 'ip link set {0} netns {1}'.format(name, pid)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)


def _configure_interface(pid, name, ip, down):
    ctx.logger.info(
        'Configuring CP with parameters: pid={0}, name={1}, ip={2}'
        .format(pid, name, ip)
    )

    if _check_if_interface_exists(pid, name):
        ctx.logger.info('Configuring CP - existing interface detected')
        _configure_existing_interface(pid, name, ip, down)
    elif _check_if_interface_exists(None, name):
        _move_host_interface_to_namespace(pid, name)
        _configure_existing_interface(pid, name, ip, down)
    else:
        ctx.logger.info('Configuring CP - new interface will be configured')
        in_name = '{0}_in'.format(name)

        _create_interfaces_pair(name, in_name)
        _configure_external_interface(name)
        _configure_internal_interface(pid, in_name, ip)

        return name, in_name


def create(**kwargs):
    name = ctx.node.properties.get('name', kwargs.get('name', None))

    if name:
        pod_name = _get_input_parameter('pod_name', kwargs)
        ip = _get_input_parameter('ip', kwargs)
        down = ctx.node.properties.get('down', kwargs.get(name, False))

        return _configure_interface(
            _get_container_pid(pod_name),
            name,
            ip,
            down
        )
