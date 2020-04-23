import os
import sys
import logging
import datetime
import configparser

from py_jama_rest_client.client import JamaClient
from py_jama_rest_client.client import APIException

logger = logging.getLogger(__name__)


def update_harms(jama_client: JamaClient, config: configparser.ConfigParser):
    # Get Script settings from config
    filter_id = None
    destination_item_type_id = None
    destination_harm_identifier_field_name = None
    destination_harm_severity_field_name = None
    destination_revised_harm_identifier_field_name = None
    destination_revised_harm_severity_field_name = None
    source_harm_severity_field_name = None
    try:
        filter_id = config.getint('SCRIPT_SETTINGS', 'destination_filter_id')
        destination_item_type_id = config.getint('SCRIPT_SETTINGS', 'destination_item_type_id')
        destination_harm_identifier_field_name = config.get('SCRIPT_SETTINGS',
                                                            'destination_harm_identifier_field_name').strip()
        destination_harm_severity_field_name = config.get('SCRIPT_SETTINGS',
                                                          'destination_harm_severity_field_name').strip()
        destination_revised_harm_identifier_field_name = config.get('SCRIPT_SETTINGS',
                                                                    'destination_revised_harm_identifier_field_name') \
            .strip()
        destination_revised_harm_severity_field_name = config.get('SCRIPT_SETTINGS',
                                                                  'destination_revised_harm_severity_field_name') \
            .strip()
        source_harm_severity_field_name = config.get('SCRIPT_SETTINGS', 'source_harm_severity_field_name').strip()

    except configparser.Error as config_error:
        logger.error("Unable to parse SCRIPT_SETTINGS because: {} Please check settings and try again."
                     .format(str(config_error)))
        exit(1)

    # Settings Loaded Begin processing.

    # Pull down source Data.
    logger.info("Fetching Filter Data")
    destination_items = None
    try:
        destination_items = jama_client.get_filter_results(filter_id)
    except APIException as error:
        logger.error("Unable to fetch filter data: {}".format(str(error)))

    # Filter down to only the item type we care about, removing texts and folders
    destination_items = [item for item in destination_items if item.get('itemType') == destination_item_type_id]

    # Create a dictionary of Harm items so that we do not pull items twice.
    harms = {}
    # for each item in destination_items we need to fetch the downstream harm and the downstream revised harm
    for item in destination_items:
        logger.info("Processing item: [{}]".format(str(item.get('id'))))
        item_type = item.get('itemType')
        item_fields = item.get('fields')
        severity_patch = None
        revised_severity_patch = None
        try:
            # fetch and update the harm severity
            if destination_harm_identifier_field_name + '$' + str(item_type) in item_fields:
                harm_reference = item_fields.get(destination_harm_identifier_field_name + '$' + str(item_type))
                if harm_reference not in harms:
                    try:
                        harms[harm_reference] = jama_client.get_item(harm_reference)
                        harm = harms[harm_reference]
                        harm_severity = harm.get('fields').get(
                            source_harm_severity_field_name + '$' + str(harm.get('itemType')))

                        # Now that we have severity create a patch object to post. unless we have no changes
                        if destination_harm_severity_field_name + '$' + str(item_type) in item_fields \
                                and harm_severity == item_fields.get(destination_harm_severity_field_name
                                                                     + '$' + str(item_type)):
                            # field is already set to the desired value.
                            logger.info("Skipping harm severity patch, there are no changes")
                        elif destination_harm_severity_field_name + '$' + str(item_type) in item_fields:
                            severity_patch = {
                                "op": "replace",
                                "path": "/fields/{}${}".format(destination_harm_severity_field_name, str(item_type)),
                                "value": harm_severity
                            }
                        else:
                            severity_patch = {
                                "op": "add",
                                "path": "/fields/{}${}".format(destination_harm_severity_field_name, str(item_type)),
                                "value": harm_severity
                            }
                    except APIException as ex:
                        logger.error("Unable to fetch referenced harm: {} Because: {}"
                                     .format(str(harm_reference), str(ex)))

            else:
                logger.info("Cannot fetch Item of Type.  Item {} has no data in {} field."
                            .format(str(item.get('id')), destination_harm_identifier_field_name))

            # Fetch and update Revised harm
            if destination_revised_harm_identifier_field_name + '$' + str(item_type) in item_fields:
                # Now update the revised harm severity
                revised_harm_reference = item_fields.get(destination_revised_harm_identifier_field_name + '$'
                                                         + str(item_type))
                if revised_harm_reference not in harms:
                    try:
                        harms[revised_harm_reference] = jama_client.get_item(revised_harm_reference)
                        revised_harm = harms[revised_harm_reference]
                        revised_harm_severity = revised_harm.get('fields').get(source_harm_severity_field_name + '$' +
                                                                               str(revised_harm.get('itemType')))
                        # Now that we have severity create a patch object to post. If there are changes
                        if destination_revised_harm_severity_field_name + '$' + str(item_type) in item_fields \
                                and revised_harm_severity == item_fields.get(
                                    destination_revised_harm_severity_field_name + '$' + str(item_type)):
                            logger.info("Skipping revised harm severity patch, there are no changes")
                        elif destination_revised_harm_severity_field_name + '$' + str(item_type) in item_fields:
                            revised_severity_patch = {
                                "op": "replace",
                                "path": "/fields/{}${}".format(destination_revised_harm_severity_field_name,
                                                               str(item_type)),
                                "value": revised_harm_severity
                            }
                        else:
                            revised_severity_patch = {
                                "op": "add",
                                "path": "/fields/{}${}".format(destination_revised_harm_severity_field_name,
                                                               str(item_type)),
                                "value": revised_harm_severity
                            }
                    except APIException as ex:
                        logger.error("Unable to fetch referenced harm: {} Because: {}"
                                     .format(str(revised_harm_reference), str(ex)))
            else:
                logger.info("Cannot fetch Item of Type.  Item {} has no data in {} field."
                            .format(str(item.get('id')), destination_revised_harm_identifier_field_name))
            # Build the patch array and patch the item.
            patches = []
            if severity_patch is not None:
                patches.append(severity_patch)
            if revised_severity_patch is not None:
                patches.append(revised_severity_patch)

            if len(patches) > 0:
                try:
                    logger.info("Patching item: {}".format(str(item.get('id'))))
                    jama_client.patch_item(item.get('id'), patches)
                except APIException as error:
                    logger.error("Unable to patch item: {} because: {}".format(str(item.get('id')), str(error)))

        except Exception as ex:
            logger.error("Unable to process item: [{}] Because: {}".format(str(item.get('id')), str(ex)))


def init_logging():
    try:
        os.makedirs('logs')
    except FileExistsError:
        pass
    current_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H_%M_%S")
    log_file = 'logs/harm-severity-updater_' + str(current_date_time) + '.log'
    logging.basicConfig(filename=log_file, level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def parse_config():
    if len(sys.argv) != 2:
        logger.error("Incorrect number of arguments supplied.  Expecting path to config file as only argument.")
        exit(1)
    current_dir = os.path.dirname(__file__)
    path_to_config = sys.argv[1]
    if not os.path.isabs(path_to_config):
        path_to_config = os.path.join(current_dir, path_to_config)

    # Parse config file.
    configuration = configparser.ConfigParser()
    configuration.read_file(open(path_to_config))
    return configuration


def create_jama_client(config: configparser.ConfigParser):
    url = None
    user_id = None
    user_secret = None
    oauth = None
    try:
        url = config.get('CLIENT_SETTINGS', 'jama_connect_url').strip()
        # Clenup URL field
        while url.endswith('/') and url != 'https://' and url != 'http://':
            url = url[0:len(url) - 1]
        # If http or https method not specified in the url then add it now.
        if not (url.startswith('https://') or url.startswith('http://')):
            url = 'https://' + url
        oauth = config.getboolean('CLIENT_SETTINGS', 'oauth')
        user_id = config.get('CLIENT_SETTINGS', 'user_id').strip()
        user_secret = config.get('CLIENT_SETTINGS', 'user_secret').strip()
    except configparser.Error as config_error:
        logger.error("Unable to parse CLIENT_SETTINGS from config file because: {}, "
                     "Please check config file for errors and try again."
                     .format(str(config_error)))
        exit(1)

    return JamaClient(url, (user_id, user_secret), oauth=oauth)


# Execute this as a script.
if __name__ == "__main__":
    # Setup logging
    init_logging()

    # Get Config File Path
    conf = parse_config()

    # Create Jama Client
    client = create_jama_client(conf)

    # Begin business logic
    update_harms(client, conf)

    logger.info("Done.")
