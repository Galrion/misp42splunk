#!/usr/bin/env python
# coding=utf-8

import json
import logging
import os
from splunk.clilib import cli_common as cli

__license__ = "LGPLv3"
__version__ = "3.0.6"
__maintainer__ = "Remi Seguy"
__email__ = "remg427@gmail.com"


def prepare_config(self):
    config_args = dict()
    # get MISP instance to be used
    misp_instance = self.misp_instance
    stanza_name = 'misp://' + misp_instance
    logging.info("stanza_name={}".format(stanza_name))
    # get MISP instance parameters
    # open local/inputs.conf
    _SPLUNK_PATH = os.environ['SPLUNK_HOME']
    app_name = 'misp42splunk'
    inputs_conf_file = _SPLUNK_PATH + os.sep + 'etc' + os.sep + 'apps' \
        + os.sep + app_name + os.sep + 'local' + os.sep + 'inputs.conf'
    if os.path.exists(inputs_conf_file):
        inputsConf = cli.readConfFile(inputs_conf_file)
        foundStanza = False
        for name, content in inputsConf.items():
            if stanza_name in name:
                mispconf = content
                foundStanza = True
                logging.info(json.dumps(mispconf))
        if not foundStanza:
            logging.error("local/inputs.conf does not contain settings for stanza: {}".format(stanza_name))
            raise Exception('local/inputs.conf does not contain any stanza %s ', str(stanza_name))
    else:
        logging.error("local/inputs.conf does not exist. Please configure misp instances first.") 
        raise Exception('local/inputs.conf does not exist. Please configure an inputs entry for %s', misp_instance)
    # get clear version of misp_key
    storage_passwords = self.service.storage_passwords
    config_args['misp_key'] = None
    for credential in storage_passwords:
        # usercreds = {'username':credential.content.get('username'),'password':credential.content.get('clear_password')}
        username = credential.content.get('username')
        if misp_instance in username and 'misp_key' in credential.content.get('clear_password'):
            misp_instance_key = json.loads(credential.content.get('clear_password'))
            config_args['misp_key'] = str(misp_instance_key['misp_key'])
            logging.info('misp_key found for instance {}'.format(misp_instance))
        if 'proxy' in username and 'misp' in username and \
                'proxy_password' in credential.content.get('clear_password'):
            proxy_password = str(json.loads(credential.content.get('clear_password')))
            logging.info('proxy_password found for misp42splunk')

    if config_args['misp_key'] is None:
        logging.error('misp_key NOT found for instance {}'.format(misp_instance))
        raise Exception('misp_key NOT found for instance  %s ', misp_instance)         
    # settings
    # get MISP settings stored in inputs.conf
    config_args['misp_url'] = mispconf['misp_url']
    logging.info("config_args['misp_url'] {}".format(config_args['misp_url']))
    if int(mispconf['misp_verifycert']) == 1:
        config_args['misp_verifycert'] = True
    else:
        config_args['misp_verifycert'] = False
    logging.info("config_args['misp_verifycert'] {}".format(config_args['misp_verifycert']))
    config_args['proxies'] = dict()
    if int(mispconf['misp_use_proxy']) == 1:
        settings_file = _SPLUNK_PATH + os.sep + 'etc' + os.sep + 'apps' \
            + os.sep + app_name + os.sep \
            + 'local' + os.sep + 'misp42splunk_settings.conf'
        if os.path.exists(settings_file):
            misp42splunk_settings = cli.readConfFile(settings_file)
            foundProxy = False
            for name, content in misp42splunk_settings.items():
                if 'proxy' in name:
                    proxy = content
                    foundProxy = True
                    logging.info("Successfully found proxy settings")
            if not foundProxy:
                logging.error("misp_use_proxy is True and local/misp42splunk_settings.conf does not contain settings for proxy") 
                raise Exception('misp_use_proxy is True and local/misp42splunk_settings.conf does not contain settings for proxy')
        else:
            logging.error("misp_use_proxy is True and local/misp42splunk_settings.conf does not exist. Please configure misp42splunk first.") 
            raise Exception("misp_use_proxy is True and local/misp42splunk_settings.conf does not exist. Please configure misp42splunk first.") 
        if proxy:
            proxy_url = '://'
            if proxy['proxy_username'] is not '':
                proxy_url = proxy_url + proxy['proxy_username'] + ':' + proxy_password + '@'
            proxy_url = proxy_url + proxy['proxy_url'] + ':' + proxy['proxy_port'] + '/'
            config_args['proxies'] = {
                "http": "http" + proxy_url,
                "https": "https" + proxy_url
            }

    # get client cert parameters
    if int(mispconf['client_use_cert']) == 1:
        config_args['client_cert_full_path'] = mispconf['client_cert_full_path']
    else:
        config_args['client_cert_full_path'] = None
    logging.info("config_args['client_cert_full_path'] {}".format(config_args['client_cert_full_path']))

    # test if client certificate file is readable
    if config_args['client_cert_full_path'] is not None:
        try:
            with open(config_args['client_cert_full_path'], 'rb'):  # open client_cert_full_path if exists and log.
                logging.info('client_cert_full_path file at %s was successfully opened', str(config_args['client_cert_full_path']))
        except IOError : # file misp_instances.csv not readable
            logging.error('client_cert_full_path file at %s not readable', str(config_args['client_cert_full_path']))
            raise Exception('client_cert_full_path file at %s not readable', str(config_args['client_cert_full_path']))

    return config_args
