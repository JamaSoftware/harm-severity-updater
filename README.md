# Harm Severity Updater
The purpose of this script is to update an item with data that is contained in an item referenced from an Item of Type 
field.  The inputs to this script are a filter, an item type, and the names of the fields that contain the referenced 
data.

# Installation
This section contains information on how to install the required dependencies for this script.

## Pre-Requisites
* [Python 3.7+](https://www.python.org/downloads/release/python-377/) If using pipenv you must use a python 3.7.X 
version.  If installing requirements manually you may use any python version including 3.8+ however testing has only
been done against python 3.7

* [py-jama-rest-client](https://pypi.org/project/py-jama-rest-client/)

* Enable the REST API on your Jama Connect instance

## Pipenv installation (Recommended)
If you do not already have Pipenv installed on your machine you can learn how to install it here: 
[https://pypi.org/project/pipenv/](https://pypi.org/project/pipenv/)

The required dependencies for this project are managed with Pipenv and can be installed by opening a terminal
to the project directory and entering the following command:
```bash
    pipenv install
```

## Manual installation
If you do not wish to use Pipenv you may manually install the required dependencies with pip.
```bash
pip install --user py-jama-rest-client
```

# Usage
This section contains information on configuration and execution the script.

## Configuration
Before you can execute the script you must configure the script via a config file.  The config file is
structured in a standard .ini file format. there is an example config.ini file included with this repo that you
may modify with your settings.  I recommend that you create a copy of the template config file and rename it to
something that is meaningful for your execution.

#### Client Settings:
This section contains settings related to connecting to your Jama Connect REST API.

* jama_connect_url: this is the URL to your Jama Connect instance

* oauth: setting this value to 'false' will instruct the client to authenticate via basic authentication.  Setting this 
value to 'true' instructs the client to use OAuth authentication protocols

* user_id: This should be either your username or clientID if using OAuth

* user_secret: This should be either your password or client_secret if using OAuth

#### Script Settings:
This section contains settings for configuration of the scripts functionality.

#### A note on terminology:
Any field that begins with 'destination' is referring to an item that will be updated i.e. a hazard or failure mode.  
Any field that begins with 'source' is referring to an item from which data will be pulled, i.e. a Harm.  
All fields are required.

* destination_filter_id: This is the API ID of the filter used to specify the location in Jama that is to be processed.
The filter should be constructed to work on a specific project, it should be public, and it should filter items under a 
specific location.

* destination_item_type: This is the API ID of the item type that should have work performed on it.

* destination_harm_identifier_field_name: The unique field name of the Item of Type field in the destination item that 
references a Harm.

* destination_harm_severity_field_name: The unique field name of the severity field in the destination item.

* destination_harm_description_field_name: The unique field name of the harm description field to be updated in 
the destination item.

* destination_revised_harm_identifier_field_name: The unique field name of of the revised harm Item of Type field in the
destination item.

* destination_revised_harm_severity_field_name: The unique field name of revised severity field in the destination item.

* destination_revised_harm_description_field_name: The unique field name of the revised harm description field to be updated 
in the destination item.

* source_harm_severity_field_name: The unique field name of the field in the source item that contains the desired data
to be retrieved and placed into the destination item. This field data is populated into the 

* source_harm_description_field_name: The unique field name of the field in the source item that contains the desired data
to be retrieved and placed into the destination item.  This field data is populated into the
<destination_harm_severity_field_name> and the <destination_revised_harm_severity_field_name>
<destination_harm_description_field_name> and the <destination_revised_harm_description_field_name> 

## Running the script

1) Open a terminal to the project directory.
2) If using pipenv enter the following(otherwise skip to step 3):
   ```bash
   pipenv shell 
   ``` 
3) Enter the following command into your terminal (Note that the script accepts one parameter and that is the path to
the config file created above):  
   ```bash 
   python harm-severity-updater.py config.ini
   ```

## Output
Execution logs will be output to the terminal as well as output to a log file in the logs/ folder located next to the 
script.
