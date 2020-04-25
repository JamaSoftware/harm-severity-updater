import os
import sys
import logging
import datetime
import configparser
from typing import Callable, Union

from py_jama_rest_client.client import JamaClient
from py_jama_rest_client.client import APIException

logger = logging.getLogger(__name__)

# This dictionary will store Items that we have already fetched and may use again.
fetched_items = {}

# This is a list of Jama core field names so that we can appropriatly apply the "$itemType" field name nomenclature
core_fields = [
    "name",
    "description",
    "documentKey",
    "globalId"
]


def fetch_item(referenced_iot_item_id):
    fetched_items[referenced_iot_item_id] = jama_client.get_item(referenced_iot_item_id)


def process_iot(item: dict,
                iot_field: str,
                dest_field: str,
                source_field: str,
                transform_function: Callable[[object], object] = None) -> Union[None, dict]:
    """
    This function will fetch the item referenced by the iot_field parameter.  Then it will get the data from the
    specified source_field in that de-referenced and fetched item and apply its value to the dest_field in item the
    original item.  Optionally a transform function may be supplied to convert the source field data into the
    appropriate form for the destination field. This may be useful for mapping pick list options or applying any other
    custom logic to the data.
    :param item: This is the destination item; it contains the iot_field, data will be moved from the src_field in the
    referenced item to the dest_field in this item.
    :param iot_field: The Unique Field Name of the Item Of Type field that contains an item reference to be fetched.
    :param dest_field: The Unique Field Name of the destination field within item
    :param source_field: The Unique Field Name of the source field within the item that is referenced by the
    referenced item of type field.
    :param transform_function: This optional function should accept the data found in source_field, and know how to
    appropriately transform and return data in an acceptable format for the dest_field.
    :return: A dictionary that represents a patch for item OR None if no changes are needed or applicable.
    """
    try:
        patch = None  # This will be the object we eventually return

        item_type_id = item.get('itemType')
        item_type_id_str = str(item_type_id)
        item_fields = item.get('fields')

        iot_field_name = iot_field
        if iot_field not in core_fields:
            iot_field_name = "{}${}".format(iot_field, item_type_id_str)

        # Check to see if IOT field has data, if not this operation is nonsense.
        if iot_field_name not in item_fields:
            logger.warning("Item [{}] has no data in Item Of Type field [{}].  Skipping."
                           .format(item_type_id_str, iot_field))
            return patch

        # Now fetch the referenced item.
        referenced_iot_item_id = item_fields.get(iot_field_name)
        if referenced_iot_item_id not in fetched_items:
            try:
                fetch_item(referenced_iot_item_id)
            except APIException:
                logger.error("Unable to fetch referenced Item of Type item [{}]. Skipping processing."
                             .format(referenced_iot_item_id))
                return patch
        referenced_iot_item = fetched_items[referenced_iot_item_id]
        referenced_item_itemtype_id = referenced_iot_item.get('itemType')

        # Get the desired data from the source field in the referenced item
        source_field_name = source_field
        if source_field not in core_fields:
            source_field_name = "{}${}".format(source_field, referenced_item_itemtype_id)
        source_data = referenced_iot_item.get('fields').get(source_field_name)

        # Perform any required data transformation
        destination_data = source_data
        if transform_function is not None:
            destination_data = transform_function(source_data)

        # Prepare a patch if required.
        dest_field_name = dest_field
        if dest_field not in core_fields:
            dest_field_name = "{}${}".format(dest_field, item_type_id_str)

        # Determine what kind of patch is needed
        if dest_field_name in item_fields and destination_data == item_fields.get(dest_field_name):
            return patch
        elif dest_field_name in item_fields:
            patch = {
                "op": "replace",
                "path": "/fields/{}".format(dest_field_name),
                "value": destination_data
            }
        else:
            patch = {
                "op": "add",
                "path": "/fields/{}".format(dest_field_name),
                "value": destination_data
            }

        return patch
    except Exception as ex:
        logger.error("Error processing Item of Type field. Source: {} Destination: {} Because: {}"
                     .format(source_field, dest_field, ex))
        return None


def update_harms(config: configparser.ConfigParser):
    # Get Script settings from config
    filter_id = None
    destination_item_type_id = None
    destination_harm_identifier_field_name = None
    destination_harm_severity_field_name = None
    destination_harm_description_field_name = None
    destination_revised_harm_identifier_field_name = None
    destination_revised_harm_severity_field_name = None
    destination_revised_harm_description_field_name = None
    source_harm_severity_field_name = None
    source_harm_description_field_name = None

    try:
        filter_id = config.getint('SCRIPT_SETTINGS', 'destination_filter_id')
        destination_item_type_id = config.getint('SCRIPT_SETTINGS', 'destination_item_type_id')
        destination_harm_identifier_field_name = config.get('SCRIPT_SETTINGS',
                                                            'destination_harm_identifier_field_name').strip()
        destination_harm_severity_field_name = config.get('SCRIPT_SETTINGS',
                                                          'destination_harm_severity_field_name').strip()
        destination_harm_description_field_name = config.get('SCRIPT_SETTINGS',
                                                             'destination_harm_description_field_name').strip()
        destination_revised_harm_identifier_field_name = config.get('SCRIPT_SETTINGS',
                                                                    'destination_revised_harm_identifier_field_name') \
            .strip()
        destination_revised_harm_severity_field_name = config.get('SCRIPT_SETTINGS',
                                                                  'destination_revised_harm_severity_field_name') \
            .strip()
        destination_revised_harm_description_field_name = config.get('SCRIPT_SETTINGS',
                                                                     'destination_revised_harm_description_field_name')\
            .strip()
        source_harm_severity_field_name = config.get('SCRIPT_SETTINGS', 'source_harm_severity_field_name').strip()
        source_harm_description_field_name = config.get('SCRIPT_SETTINGS', 'source_harm_description_field_name').strip()

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

    # for each item in destination_items we need to fetch the downstream harm and the downstream revised harm
    for item in destination_items:
        logger.info("Processing item: [{}]".format(str(item.get('id'))))

        patches = [process_iot(item,
                               destination_harm_identifier_field_name,
                               destination_harm_severity_field_name,
                               source_harm_severity_field_name),
                   process_iot(item,
                               destination_harm_identifier_field_name,
                               destination_harm_description_field_name,
                               source_harm_description_field_name),
                   process_iot(item,
                               destination_revised_harm_identifier_field_name,
                               destination_revised_harm_severity_field_name,
                               source_harm_severity_field_name),
                   process_iot(item,
                               destination_revised_harm_identifier_field_name,
                               destination_revised_harm_description_field_name,
                               source_harm_description_field_name)
                   ]

        patches = [patch for patch in patches if patch is not None]

        if len(patches) > 0:
            try:
                logger.info("Patching item: {}".format(str(item.get('id'))))
                jama_client.patch_item(item.get('id'), patches)
            except APIException as error:
                logger.error("Unable to patch item: {} because: {}".format(str(item.get('id')), str(error)))


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
    jama_client = create_jama_client(conf)

    # Begin business logic
    update_harms(conf)

    logger.info("Done.")
