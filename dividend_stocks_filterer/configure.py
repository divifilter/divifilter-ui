import logging

from parse_it import ParseIt

logger = logging.getLogger(__name__)


def read_configurations(config_folder: str = "config") -> dict:
    """
    Will create a config dict that includes all of the configurations for terraformize by aggregating from all valid
    config sources (files, envvars, cli args, etc) & using sane defaults on config params that are not declared

    Arguments:
        :param config_folder: the folder which all configuration file will be read from recursively

    Returns:
        :return config: a dict of all configurations needed for terraformize to work
    """
    logger.info("Reading configuration variables")

    config = {}
    parser = ParseIt(config_location=config_folder, recurse=True)
    config["db_host"] = parser.read_configuration_variable("db_host")
    config["db_port"] = parser.read_configuration_variable("db_port", default_value=3306)
    config["db_user"] = parser.read_configuration_variable("db_user", default_value="root")
    config["db_pass"] = parser.read_configuration_variable("db_pass")
    config["db_schema"] = parser.read_configuration_variable("db_schema", default_value="defaultdb")
    config["ga_measurement_id"] = parser.read_configuration_variable("ga_measurement_id", default_value="")
    return config
