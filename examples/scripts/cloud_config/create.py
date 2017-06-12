#!/usr/bin/env python

try:
    import yaml
except ImportError:
    import pip
    pip.main(['install', 'pyyaml'])
    import yaml

import base64
from cloudify import ctx
from cloudify.state import ctx_parameters as inputs


if __name__ == '__main__':

    cloud_config = inputs['cloud_config']
    ctx.logger.debug('cloud_config: {0}'.format(cloud_config))
    cloud_config_yaml = yaml.dump(cloud_config)
    cloud_config_string = str(cloud_config_yaml).replace('!!python/unicode ', '')
    cloud_config_string = '#cloud-config\n' + cloud_config_string
    ctx.logger.debug('cloud_config_string: {0}'.format(cloud_config_string))

    if ctx.node.properties['resource_config'].get('encode_base64'):
        cloud_config_string = base64.encodestring(cloud_config_string)
        ctx.logger.debug('cloud_config_string: {0}'.format(cloud_config_string))

    ctx.instance.runtime_properties['cloud_config'] = cloud_config_string
