#!/usr/bin/env python

from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

if __name__ == '__main__':
    if inputs.get('configuration'):
        ctx.logger.info("Copy configuration to runtime properties")
        ctx.logger.debug("Configuration: {}".format(
            str(inputs['configuration'])))
        ctx.instance.runtime_properties[
            'configuration'] = inputs['configuration']
