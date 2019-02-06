#!/usr/bin/env python
# coding=utf-8
#
# Extract IOC's from MISP
#
# Author: Xavier Mertens <xavier@rootshell.be>
# Author: Remi Seguy <remg427@gmail.com>
#
# Copyright: LGPLv3 (https://www.gnu.org/licenses/lgpl-3.0.txt)
# Feel free to use the code, but please share the changes you've made
#

from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import requests
import json

from splunklib.searchcommands import dispatch, ReportingCommand, Configuration, Option, validators
import logging
from misp_common import prepare_config

__author__     = "Remi Seguy"
__license__    = "LGPLv3"
__version__    = "2.1.0"
__maintainer__ = "Remi Seguy"
__email__      = "remg427@gmail.com"


@Configuration(requires_preop=False)
class mispgetioc(ReportingCommand):
    """ get the attributes from a MISP instance.
    ##Syntax
    .. code-block::
        | mispgetioc last=<int>(d|h|m)
        | mispgetioc event=<id1>(,<id2>,...)
    ##Description
    """
    # Superseede MISP instance for this search
    misp_instance = Option(
        doc='''
        **Syntax:** **misp_instance=instance_name*
        **Description:**MISP instance parameters as decibed in lookup/misp_instances.csv.''',
        require=False)
    misp_url = Option(
        doc='''
        **Syntax:** **misp_url=***<MISP URL>*
        **Description:**URL of MISP instance.''',
        require=False, validate=validators.Match("misp_url", r"^https?:\/\/[0-9a-zA-Z\-\.]+(?:\:\d+)?$"))
    misp_key = Option(
        doc='''
        **Syntax:** **misp_key=***<AUTH_KEY>*
        **Description:**MISP API AUTH KEY.''',
        require=False, validate=validators.Match("misp_key", r"^[0-9a-zA-Z]{40}$"))
    misp_verifycert = Option(
        doc = '''
        **Syntax:** **misp_verifycert=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Verify or not MISP certificate.''',
        require=False, validate=validators.Boolean())
    # MANDATORY: eventid XOR last
    eventid         = Option(
        doc = '''
        **Syntax:** **eventid=***id1(,id2,...)*
        **Description:**list of event ID(s). **eventid**, **last** and **date_from** are mutually exclusive''',
        require=False, validate=validators.Match("eventid",r"^[0-9,]+$"))
    last            = Option(
        doc = '''
        **Syntax:** **last=***<int>d|h|m*
        **Description:**publication duration in day(s), hour(s) or minute(s). **eventid**, **last** and **date_from** are mutually exclusive''',
        require=False, validate=validators.Match("last",r"^[0-9]+[hdm]$"))
    date_from       = Option(
        doc = '''
        **Syntax:** **date_from=***date_string"*
        **Description:**starting date. **eventid**, **last** and **date_from** are mutually exclusive''',
        require=False)
    date_to         = Option(
        doc = '''
        **Syntax:** **date_to=***date_string"*
        **Description:**(optional)ending date in searches with date_from. if not set default is now''',
        require=False)
    onlyids         = Option(
        doc = '''
        **Syntax:** **onlyids=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**deprecated use to_ids option instead.''',
        require=False, validate=validators.Boolean())
    to_ids          = Option(
        doc = '''
        **Syntax:** **to_ids=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Boolean to search only attributes with the flag "to_ids" set to true.''',
        require=False, validate=validators.Boolean())
    published       = Option(
        doc = '''
        **Syntax:** **published=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**select only published events (for option from to) .''',
        require=False, validate=validators.Boolean())
    category        = Option(
        doc = '''
        **Syntax:** **category=***CSV string*
        **Description:**Comma(,)-separated string of categories to search for. Wildcard is %.''',
        require=False)
    type            = Option(
        doc = '''
        **Syntax:** **type=***CSV string*
        **Description:**Comma(,)-separated string of categories to search for. Wildcard is %.''',
        require=False)
    tags            = Option(
        doc = '''
        **Syntax:** **tags=***CSV string*
        **Description:**Comma(,)-separated string of tags to search for. Wildcard is %.''',
        require=False)
    not_tags        = Option(
        doc = '''
        **Syntax:** **not_tags=***CSV string*
        **Description:**Comma(,)-separated string of tags to exclude from results. Wildcard is %.''',
        require=False)
    limit         = Option(
        doc = '''
        **Syntax:** **limit=***<int>*
        **Description:**define the limit for each MISP search; default 10000. 0 = no pagination.''',
        require=False, validate=validators.Match("limit",     r"^[0-9]+$"))
    getuuid         = Option(
        doc = '''
        **Syntax:** **getuuid=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Boolean to return attribute UUID.''',
        require=False, validate=validators.Boolean())
    getorg          = Option(
        doc = '''
        **Syntax:** **getorg=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Boolean to return the ID of the organisation that created the event.''',
        require=False, validate=validators.Boolean())
    geteventtag     = Option(
        doc = '''
        **Syntax:** **geteventtag=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Boolean to return also event tag(s). By default only attribute tag(s) are returned.''',
        require=False, validate=validators.Boolean())
    pipesplit     = Option(
        doc = '''
        **Syntax:** **pipesplit=***<1|y|Y|t|true|True|0|n|N|f|false|False>*
        **Description:**Boolean to split multivalue attributes into 2 attributes.''',
        require=False, validate=validators.Boolean())


    @Configuration()
    def map(self, records):
        # self.logger.debug('mispgetioc.map')
        return records

    def reduce(self, records):

        # Phase 1: Preparation
        my_args = prepare_config(self)
        my_args['misp_url'] = my_args['misp_url'] + '/attributes/restSearch'

        # build search JSON object
        body_dict = { "returnFormat": "json",
                      "withAttachments": False,
                      "deleted": False
                    }

        # check that ONE of mandatory fields is present
        mandatory_arg = 0
        if self.eventid:
            mandatory_arg = mandatory_arg + 1
        if self.last:
            mandatory_arg = mandatory_arg + 1
        if self.date_from:
            mandatory_arg = mandatory_arg + 1

        if mandatory_arg == 0:
            logging.error('Missing "eventid", "last" or "date_from" argument')
            raise Exception('Missing "eventid", "last" or "date_from" argument')
        elif mandatory_arg > 1:
            logging.error('Options "eventid", "last" and "date_from" are mutually exclusive')
            raise Exception('Options "eventid", "last" and "date_from" are mutually exclusive')

        # Only ONE combination was provided
        if self.eventid:
            if "," in self.eventid:
                event_criteria = {}
                event_list = self.eventid.split(",")
                event_criteria['OR'] = event_list
                body_dict['eventid'] = event_criteria
            else:
                body_dict['eventid'] = self.eventid
            logging.info('Option "eventid" set with %s', body_dict['eventid'])
        elif self.last:
            body_dict['last'] = self.last
            logging.info('Option "last" set with %s', body_dict['last'])
        else:
            body_dict['from'] = self.date_from
            logging.info('Option "date_from" set with %s', body_dict['from'])
            if self.date_to:
                body_dict['to'] = self.date_to
                logging.info('Option "date_to" set with %s', body_dict['to'])
            else:
                logging.info('Option "date_to" will be set to now().')

        # set proper headers
        headers = {'Content-type': 'application/json'}
        headers['Authorization'] = my_args['misp_key']
        headers['Accept'] = 'application/json'

        # Search pagination
        pagination = True
        other_page = True
        page = 1
        l = 0
        if self.limit is not None:
            if int(self.limit) == 0:
                pagination = False
            else:
                limit = int(self.limit)
        else:
            limit = 10000

        #Search parameters: boolean and filter
        if self.onlyids is True:
            body_dict['to_ids'] = True
        if self.to_ids is True:
            body_dict['to_ids'] = True
        if self.published is True:
            body_dict['published'] = True
        if self.geteventtag is True:
            body_dict['includeEventTags'] = True
        if self.category is not None:
            cat_criteria = {}
            cat_list = self.category.split(",")
            cat_criteria['OR'] = cat_list
            body_dict['category'] = cat_criteria
        if self.type is not None:
            type_criteria = {}
            type_list = self.type.split(",")
            type_criteria['OR'] = type_list
            body_dict['type'] = type_criteria
        if self.tags is not None or self.not_tags is not None:
            tags_criteria = {}
            if self.tags is not None:
                tags_list = self.tags.split(",")
                tags_criteria['OR'] = tags_list
            if self.not_tags is not None:
                tags_list = self.not_tags.split(",")
                tags_criteria['NOT'] = tags_list
            body_dict['tags'] = tags_criteria

        # output filter parameters
        if self.getuuid is True:
            my_args['getuuid'] = True
        else:
            my_args['getuuid'] = False
        if self.getorg is True:
            my_args['getorg'] = True
        else:
            my_args['getorg'] = False
        if self.pipesplit is True:
            my_args['pipe'] = True
        else:
            my_args['pipe'] = False

        results = []
        # add colums for each type in results
        typelist = []
        while other_page:
            if pagination == True:
                body_dict['page'] = page
                body_dict['limit'] = limit

            body = json.dumps(body_dict)
            logging.info('INFO MISP REST API REQUEST: %s', body)
            # search
            r = requests.post(my_args['misp_url'], headers=headers, data=body, verify=my_args['misp_verifycert'], proxies=my_args['proxies'])
            # check if status is anything other than 200; throw an exception if it is
            r.raise_for_status()
            # response is 200 by this point or we would have thrown an exception
            response = r.json()
            if 'response' in response:
                if 'Attribute' in response['response']:
                    l = len(response['response']['Attribute'])
                    for a in response['response']['Attribute']:
                        v = {}
                        v['misp_description'] = 'MISP e' + str(a['event_id']) + ' attribute ' + str(a['uuid']) + ' of type "' \
                         + str(a['type']) + '" in category "' + str(a['category']) + '" (to_ids:' + str(a['to_ids']) + ')'
                        v['misp_category'] = str(a['category'])
                        v['misp_attribute_id'] = str(a['id'])
                        v['misp_event_id'] = str(a['event_id'])
                        v['misp_timestamp'] = str(a['timestamp'])
                        v['misp_to_ids'] = str(a['to_ids'])
                        tag_list = []
                        if 'Tag' in a:
                            for tag in a['Tag']:
                                try:
                                    tag_list.append(str(tag['name']))
                                except Exception:
                                    pass
                        v['misp_tag'] = tag_list
                        # include ID of the organisation that created the attribute if requested
                        # in previous version this was the ORG name ==> create lookup
                        if 'Event' in a and my_args['getorg']:
                            v['misp_orgc_id'] = str(a['Event']['orgc_id'])
                        # include attribute UUID if requested
                        if my_args['getuuid']:
                            v['misp_attribute_uuid'] = str(a['uuid'])
                        # handle object and multivalue attributes
                        v['misp_object_id'] = str(a['object_id'])
                        current_type = str(a['type'])
                        # combined: not part of an object AND multivalue attribute QND to be split
                        if int(a['object_id']) == 0 and '|' in current_type and my_args['pipe'] is True: 
                            mv_type_list = current_type.split('|')
                            mv_value_list = str(a['value']).split('|')
                            left_v = v.copy()
                            left_v['misp_type'] = mv_type_list.pop()
                            left_v['misp_value'] = mv_value_list.pop()
                            results.append(left_v)
                            if left_v['misp_type'] not in typelist:
                                typelist.append(left_v['misp_type'])
                            right_v= v.copy()
                            right_v['misp_type'] = mv_type_list.pop()
                            right_v['misp_value'] = mv_value_list.pop()
                            results.append(right_v)
                            if right_v['misp_type'] not in typelist:
                                typelist.append(right_v['misp_type'])
                        else:
                            v['misp_type'] = current_type
                            v['misp_value'] = str(a['value'])
                            results.append(v)
                            if current_type not in typelist:
                                typelist.append(current_type)

            if pagination == True:
                if l < limit:
                    other_page = False
                else:
                    page = page + 1
            else:
                other_page = False

        logging.info(json.dumps(typelist))

        output_dict = {}
        #relevant_cat = ['Artifacts dropped', 'Financial fraud', 'Network activity','Payload delivery','Payload installation']
        for r in results:
            if int(r['misp_object_id']) == 0: # not an object
                key = str(r['misp_event_id']) + '_' +  r['misp_attribute_id']
                is_object_member = False
            else: # this is a  MISP object
                key = str(r['misp_event_id']) + '_object_' + str(r['misp_object_id'])
                is_object_member = True           
            if key not in output_dict:
                v = r                
                for t in typelist:
                    misp_t = 'misp_' + t.replace('-', '_').replace('|','_p_')
                    if t == r['misp_type']:
                        v[misp_t] = r['misp_value']
                    else:
                        v[misp_t] = ''
                category = []
                category.append(r['misp_category'])
                v['misp_category'] = category
                if is_object_member is True:
                    v['misp_type'] = 'misp_object'
                    v['misp_value'] = r['misp_object_id']
                output_dict[key] = v
            else:
                v = output_dict[key]
                misp_t = 'misp_' + r['misp_type'].replace('-', '_')
                v[misp_t] = r['misp_value'] # set value for relevant type
                category = v['misp_category'] 
                if r['misp_category'] not in category: # append category 
                    category.append(r['misp_category'])
                    v['misp_category'] = category
                if is_object_member is False:
                    misp_type = r['misp_type'] + '|' + v['misp_type']
                    v['misp_type'] = misp_type
                    misp_value = r['misp_value'] + '|' + v['misp_value']
                    v['misp_value'] = misp_value
                output_dict[key] = v
            logging.debug(json.dumps(output_dict))
        
        for k,v in output_dict.items():
            yield v

if __name__ == "__main__":
    # set up logging suitable for splunkd consumption
    logging.root
    logging.root.setLevel(logging.ERROR)
    dispatch(mispgetioc, sys.argv, sys.stdin, sys.stdout, __name__)
