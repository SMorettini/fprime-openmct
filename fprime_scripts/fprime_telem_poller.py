from fprime_gds.common.pipeline.standard import StandardPipeline
from fprime_gds.common.utils.config_manager import ConfigManager
from fprime_gds.common.history.chrono import ChronologicalHistory

from fprime_gds.executables.cli import ParserBase, StandardPipelineParser
from typing import Any, Dict, Tuple

import requests 
import time 

import json



class TelemPipeline(StandardPipeline):
    """
    The Telemetry Pipeline class inherits from the F-Prime GDS Standard Pipeline Object for Telemetry Polling.
    It includes the following data members:

    1. StandardPipeline member variables -> Includes Dictionaries, Coders, Object History, Filing, and Transport Info
    2. telem_chron_hist -> Chronological History Object that will request new telemetry
    3. telem_hist -> List where raw telemetry objects requested by telem_chron_hist will be stored
    4. telem_data -> Contains list of processed telemetry objects in the format that OpenMCT will accept
    5. telem_init_states -> Contains dictionary of telemetry object names and their immediate value. Used to initialize values and define the telemetry states to be processed by OpenMCT server 
    6. telem_init_json -> Contains JSON of telemetry object names and their value. Saved in OpenMCT directory and used by OpenMCT server to define initial telemetry states.
    7. max_state_count -> Used to keep count of the largest number telemetry objects recieved by the pipeline in a single telemetry request
    8. json_writeable -> Used to determine if heli_states contains telemetry information. If true, the data can be written to a JSON that OpenMCT will accept
    """
    def __init__(self, connection_ip="127.0.0.1", connection_port=50050, dict_path="", log_path=""):
        StandardPipeline.__init__(self)
        self.setup(ConfigManager(), dict_path, log_path)
        self.connect(connection_ip, connection_port)
        self.telem_chron_hist = ChronologicalHistory()
        self.coders.register_channel_consumer(self.telem_chron_hist)
        self.telem_hist = []
        self.telem_data = []
        self.telem_init_states = {}
        self.telem_init_json = {}
        self.max_state_count = 0
        self.json_writeable = False

    def get_telem_hist(self):
        return self.telem_hist

    def update_telem_hist(self):
        self.telem_hist = self.telem_chron_hist.retrieve_new() #self.histories.channels.retrieve_new()
        self.telem_chron_hist.clear()
        #print(self.telem_hist)
        if (len(self.telem_hist) > self.max_state_count):
            self.max_state_count = len(self.telem_hist)

    def set_telem_json(self):
        self.telem_data = []
        for hist in self.telem_hist:
            self.json_writeable = True

            #check for structs
            if isinstance(hist.get_val(), dict):
                #print(hist.get_val().items())
                i = 0
                for key, val in hist.get_val().items():
                    hist_name = str(hist.template.comp_name) + '.' + str(hist.template.name) + '.' + hist.template.ch_type_obj.__name__[hist.template.ch_type_obj.__name__.find('::'):].replace('::', '') + '.' + key
                    #print(hist_name)

                    hist_data = {
                                'name': hist_name, 
                                'data': {
                                        'id':hist.id+i,
                                        'val': val,
                                        'time':hist.time.to_readable()
                                        }
                                }
                    
                    self.telem_data.append(hist_data)

                    if self.json_writeable:
                        self.telem_init_states[hist_name] = val

                    i = i + 1

            else: 
                hist_name = str(hist.template.comp_name) + '.' + str(hist.template.name)
                hist_data = {
                            'name': hist_name, 
                            'data': {
                                    'id':hist.id,
                                    'val':hist.get_val(),
                                    'time':hist.time.to_readable()
                                    }
                            }
                    
                self.telem_data.append(hist_data)

                if self.json_writeable:
                    self.telem_init_states[hist_name] = hist.get_val()




    def write_telem_json(self, fname="openmct/initial_states.json"):
        self.telem_init_json = json.dumps(self.telem_init_states, indent=4)
        #print(len(self.telem_init_states))
        with open(fname, "w") as outfile:
            outfile.write(self.telem_init_json)

    def post_telem(self, uri="http://127.0.0.1:4052/fprime_telem"):
        requests.post(uri, json={'name': 'heli', 'telem': self.telem_data}) 

class OpenMCTTelemetryPollerParser(ParserBase):
    """  GDS style argument parser used to add an argument specifically for this script

    GDS parsers define two methods. `get_arguments` that returns a dictionary of flag tuples to a dictionary of key word
    arguments provided to argparse. The tuple (keys) are the "arg values" supplied to `argparse.Parser.add_argument()`
    and the value of the is the "kwargs" supplied.

    `handle_arguments` takes in `args` and keyword arguments. This function allows users to validate, update, and derive
    from the arguments received.
    """

    def get_arguments(self) -> Dict[Tuple[str, ...], Dict[str, Any]]:
        """ Get the arguments to add into the parser system

        Specifically add a channel-name argument driven from --channel-name.

        Return:
            tuple of flags to argparse key word arguments
        """
        return {
            ("--openmct-uri",): {
                "dest": "openmct_uri",
                "type": str,
                "default": "http://127.0.0.1:4052/fprime_telem",
                "help": "URI of the OpenMCT Server. The URI at which the F-Prime telemetry will be broadcasted.",
                "required": False
            },
            ("--openmct-telem-rate",): {
                "dest": "openmct_telem_rate",
                "type": float,
                "default": 0.5,
                "help": "Rate(in Hz) at which we want to poll the F-Prime Telemetry Pipeline for new telemetry",
                "required": False
            }
        }

    def handle_arguments(self, args, **kwargs):
        """ Do no special argument processing

        Handle arguments can be used to process arguments for later user (e.g. derive special arguments, validate
        arguments passed in, etc). Users should ensure to pass out an argument namespace that is, or is a modified copy
        of, the supplied args.

        Args:
            args: namespace containing arguments passed in. Must be returned, or copied then modified, then returned.
            **kwargs: key-word arguments passed in to allow local adjustment. unused.
        """
        return args

#Set up and Process Command Line Arguments
arguments, _ = ParserBase.parse_args([StandardPipelineParser, OpenMCTTelemetryPollerParser],
                                             description="OpenMCT Telemetry Polling Parser",
                                             client=True  # This is a client script, thus client=True must be specified
                                             )

# instantiate the GDS and connect to the Deployment
telem_pipeline = TelemPipeline(connection_ip=arguments.tts_addr, 
                               connection_port=arguments.tts_port,
                               dict_path=arguments.dictionary,
                               log_path=arguments.logs)

# Continuously poll for telemetry from the F-Prime GDS Pipeline
write_json = True
i = 0
while True:
    #Poll the F-Prime GDS Pipeline for telemetry, and update the latest telemetry JSON
    telem_pipeline.update_telem_hist() 
    telem_pipeline.set_telem_json()
    
    #Post Telemetry Information to the server address OpenMCT is listening on
    telem_pipeline.post_telem(arguments.openmct_uri)

    time.sleep(1/arguments.openmct_telem_rate)
    i = i+1


