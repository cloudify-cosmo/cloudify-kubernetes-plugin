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


def _image_exisis(name):
    ctx.logger.info('Checking if image {0} does exist'.format(name))

    command = 'docker images {0} -q'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))

    return bool(sudo(command))


def _build(name, dockerfile_content):
    ctx.logger.info('Building image {0} ...'.format(name))

    command = 'echo "" > {0}_temp.dockerfile'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)

    for line in dockerfile_content:
        command = 'echo "{0}" >> {1}_temp.dockerfile'.format(line, name)
        ctx.logger.info('Executing command: {0}'.format(command))
        sudo(command)

    command = 'docker build -t {0} -f {0}_temp.dockerfile .'.format(name)
    ctx.logger.info('Executing command: {0}'.format(command))
    sudo(command)

    ctx.logger.info('Build success')


def create(**kwargs):
    name = _get_input_parameter('name', kwargs)
    dockerfile_content = _get_input_parameter('dockerfile_content', kwargs)

    ctx.logger.info('Docker image builder started for image {0}'.format(name))

    if not _image_exisis(name):
        _build(name, dockerfile_content)
        return

    ctx.logger.warn('Image {0} already exists. Exiting.'.format(name))
