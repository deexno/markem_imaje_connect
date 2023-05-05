import re
import socket
from datetime import datetime


class Utils(object):
    @staticmethod
    def string_to_byte(string):
        return (
            string.encode()
            .decode("unicode_escape")
            .encode("raw_unicode_escape")
        )

    @staticmethod
    def dec_to_hex(number: int) -> str:
        return "{:02x}".format(int(number))

    @staticmethod
    def hex_to_text(hex_string: str) -> str:
        return bytes.fromhex(hex_string).decode("utf-8")

    @staticmethod
    def extract_response_code(response):
        if isinstance(response, list):
            return True if response[0] == "06" else False
        else:
            return False

    @staticmethod
    def calculate_checksum(command) -> str:
        hex_array = command.split(r"\x")[1:]
        check_sum_dec = 0

        for hex_num in hex_array:
            check_sum_dec = int(check_sum_dec) ^ int(f"0x{hex_num}", 16)

        return f"{command}\\x{Utils.dec_to_hex(check_sum_dec)}"


class Printer(object):
    def __init__(self, printer_ip: str, printer_port: int = 2101) -> None:
        """
        Constructs all the necessary attributes for the printer object.

        Parameters
        ----------
            printer_ip : str
                The IP-Address of the Printer
            printer_port : int, optional
                The Network Port of the Printer (by default 2101)
        """

        self.ip: str = printer_ip
        self.port: int = printer_port

    def send_command(self, command):
        try:
            print_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print_socket.connect((self.ip, self.port))
            print_socket.send(Utils.string_to_byte(command))
            response = print_socket.recv(1024)
            print_socket.close()

            return [format(x, "02x") for x in response]
        except Exception as e:
            return e

    def get_v24_dialog(self) -> bool:
        """
        Provides a check to identify if the printer is "ready" to dialog,
        and may be sent before every exchange. Attention: It says nothing about
        whether the printer is on or off!

        Parameters
        ----------
        None

        Returns
        -------
        return_code : Bool
            Returns whether the command was successfully executed or not.

            True = ready to dialog\n
            False = not ready to dialog
        """

        return Utils.extract_response_code(self.send_command("\\x05"))

    def start_stop_printer(self, mode: int) -> bool:
        """
        Start/Stop the printer

        Parameters
        ----------
        mode : int
            Determines whether the printer should be started,
            stopped shortly or stopped for a long time.

            0 = long shutdown (Stops the printer and starts an auto-cleaning)\n
            1 = short shutdown (Stops the printer)\n
            255 = start-up

        Returns
        -------
        return_code : Bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure
        """

        return Utils.extract_response_code(
            self.send_command(
                Utils.calculate_checksum(
                    f"\\x30\\x00\\x01\\x{Utils.dec_to_hex(mode)}"
                )
            )
        )

    def get_autodating_table(self) -> list:
        """
        Request autodating table - Current Date time set on the Printer

        Parameters
        ----------
        None

        Returns
        -------
        return_code : Bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        datetime : datetime, None
            Returns the currently stored Date & time as Datetime string
        """

        response = self.send_command("\\xD6\\x00\\x00\\xD6")

        if Utils.extract_response_code(response):
            data = Utils.hex_to_text("".join(response[4:26]))
            date_string = re.sub(r"[^0-9]", "", data)
            autodating_table = datetime.strptime(date_string, "%S%M%H%d%m%y")
            return True, autodating_table
        else:
            return False, None

    def set_autodating_table(self, date_time: datetime) -> int:
        """
        Set autodating table.

        Parameters
        ----------
        date_time : datetime
            The date & time to be set on the printer

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure
        """

        date_time_format = "\\x%S\\x%M\\x%H\\x%d\\x%m\\x%y"

        return Utils.extract_response_code(
            self.send_command(
                Utils.calculate_checksum(
                    "\\xC8\\x00\\x07"
                    f"{date_time.strftime(date_time_format)}"
                    "\\x20"
                )
            )
        )

    def set_external_variable(self, jet_id: int, variables: list) -> int:
        """
        Update the external variables

        Parameters
        ----------
        jet_id : int
            Determines from which printhead/jet the variable should be set.
            Normally a number between 1-4

        variable : list
            A list of strings to be set as external variables. 1-10 variables
            can be set.

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure
        """

        if jet_id > self.get_number_of_available_jets()[1]:
            print(
                "Attention, it seems that you are trying to set the external "
                "variables from a non-existent jet! This can lead to dramatic "
                "problems!"
            )

        variables_hex = ""
        content_length = 1

        for variable in variables:
            content_length = content_length + len(variable) + 2
            variable_hex = "".join([f"\\x{ord(c):02x}" for c in variable])
            variables_hex += f"\\x12{variable_hex}\\x12"

        content_length = "{:04x}".format(content_length)

        return Utils.extract_response_code(
            self.send_command(
                Utils.calculate_checksum(
                    f"\\x5B"
                    f"\\x{content_length[:2]}\\x{content_length[2:]}"
                    f"\\x{Utils.dec_to_hex(jet_id)}"
                    f"{variables_hex}"
                )
            )
        )

    def get_jet_counter(self, jet_id: int = 1) -> list:
        """
        Request current counters. This counter is increased by 1 each time a
        print gets performed.

        Parameters
        ----------
        jet_id : int
            Determines from which printhead/jet the counter should be read.
            Normally a number between 1-4

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        counter : int
            Returns the counter for the respective printhead
        """

        if jet_id > self.get_number_of_available_jets()[1]:
            print(
                "Attention, it seems that you are trying to get the jet "
                "counter of a non-existent jet. This can lead to "
                "unpredictable problems."
            )

        response = self.send_command(
            Utils.calculate_checksum(
                f"\\x39\\x00\\x01\\x{Utils.dec_to_hex(jet_id)}"
            )
        )

        if Utils.extract_response_code(response):
            counter_data = Utils.hex_to_text("".join(response[4:13]))
            return True, int(counter_data)
        else:
            return False, 0

    def reset_jet_counter(self, jet_id: int) -> int:
        """
        Reset current counters

        Parameters
        ----------
        jet_id : int
            Determines from which printhead/jet the counter should be reset.
            Normally a number between 1-4

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure
        """

        if jet_id > self.get_number_of_available_jets()[1]:
            print(
                "Attention, it seems that you are trying to reset the jet "
                "counter of a non-existent jet. This can lead to "
                "unpredictable problems."
            )

        return Utils.extract_response_code(
            self.send_command(
                Utils.calculate_checksum(
                    f"\\x3A\\x00\\x01\\x{Utils.dec_to_hex(jet_id)}"
                )
            )
        )

    def get_jet_status(self, jet_id: int) -> list:
        """
        Request jet status

        Parameters
        ----------
        jet_id : int
            Determines from which printhead/jet the status should be checked.
            Normally a number between 1-4

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        jet_status : str, None
            Returns the status of the jet
        """

        if jet_id > self.get_number_of_available_jets()[1]:
            print(
                "Attention, it seems that you are trying to get the status of "
                "a non-existent jet. This can lead to unpredictable problems."
            )

        available_status = {
            "00": "Jet stopped",
            "01": "Jet in start-up phase",
            "02": "Jet in refresh",
            "03": "Jet in stability check",
            "04": "Jet in solvent feed",
            "05": "Jet in nozzle unclog",
            "06": "Adjustment",
            "07": "Jet running",
        }

        response = self.send_command(
            Utils.calculate_checksum(
                f"\\x32\\x00\\x01\\x{Utils.dec_to_hex(jet_id)}"
            )
        )

        if Utils.extract_response_code(response):
            return True, available_status[response[4]]
        else:
            return False, None

    def get_jet_speed(self, jet_id: int) -> list:
        """
        Request jet speed and phase

        Parameters
        ----------
        jet_id : int
            Determines from which printhead/jet the status should be checked.
            Normally a number between 1-4

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        jet_speed : float, None
            Returns the jet speed of the jet in m/s
        """

        response = self.send_command(
            Utils.calculate_checksum(
                f"\\x33\\x00\\x01\\x{Utils.dec_to_hex(jet_id)}"
            )
        )

        if Utils.extract_response_code(response):
            return True, float(response[4]) / 10
        else:
            return False, None

    def get_number_of_available_jets(self) -> list:
        """
        Get the number the jets currently available

        Parameters
        ----------
        None

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        number_of_jets : int, None
            Returns the number of jets. Normally a number between 1-4
        """

        count = 0
        printer_faults = self.get_printer_faults()

        if printer_faults[0]:
            for key, value in printer_faults[1].items():
                if "not_present" in key:
                    if int(value) == 0:
                        count += 1

            return True, count
        else:
            return False, None

    def get_parameters(self) -> list:
        """
        Request printer parameters

        Parameters
        ----------
        None

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        parameters : dict, None
            Returns the parameters
        """

        response = self.send_command("\\x20\\x00\\x00\\x20")

        if Utils.extract_response_code(response):
            data = Utils.hex_to_text("".join(response[4:30]))
            parameters_dict = {
                "motor_speed": int(data[0:4]),
                "pressure": float(data[5:9].replace(",", ".")),
                "visco_filling_times": int(data[10:12]),
                "additive_added": int(data[13:15]),
                "average_jet_speed": float(data[16:20].replace(",", ".")),
                "temperature_of_electronics": int(data[21:23]),
                "temperature_of_ink_circuit": int(data[24:26]),
            }

            return True, parameters_dict
        else:
            return False, None

    def get_printer_faults(self) -> list:
        """
        Request printer faults

        Parameters
        ----------
        None

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure

        faults : dict, None
            Returns the faults
        """

        response = self.send_command("\\x3B\\x00\\x00\\x3B")

        if Utils.extract_response_code(response):
            # Convert the hex numbers to binary so that the error bits can be
            # read out afterwards.
            response_bin = [bin(int(i, 16))[2:].zfill(8) for i in response]

            printer_faults = response_bin[4:7]
            jet_faults = [
                response_bin[7:10],
                response_bin[10:13],
                response_bin[13:16],
                response_bin[16:19],
            ]

            faults_dict = {
                "ink_level_low": printer_faults[0][7],
                "pressure_error": printer_faults[0][6],
                "cpu_hw_error": printer_faults[0][5],
                "memory_lost": printer_faults[0][4],
                "head_1_faulty": printer_faults[0][3],
                "head_2_faulty": printer_faults[0][2],
                "motor_cycle_fault": printer_faults[0][1],
                "pigmented_ink_circuit_fault": printer_faults[0][0],
                "autodating_fault": printer_faults[1][2],
                "ram_fault": printer_faults[1][1],
                "rom_fault": printer_faults[1][0],
                "v24_fault": printer_faults[2][7],
                "recovery_tank_too_full": printer_faults[2][6],
                "ink_tank_too_full": printer_faults[2][5],
                "accu_empty": printer_faults[2][4],
                "temp_fault": printer_faults[2][3],
                "viscosity_fault": printer_faults[2][2],
                "fan_fault": printer_faults[2][1],
                "additive_fault": printer_faults[2][0],
            }

            for jet_id, faults in enumerate(jet_faults):
                faults_dict.update(
                    {
                        f"j{jet_id}_printing_hardware_fault": faults[0][7],
                        f"j{jet_id}_frame_generator_fault": faults[0][2],
                        f"j{jet_id}_char_generator_fault": faults[0][1],
                        f"j{jet_id}_cover_fault": faults[1][3],
                        f"j{jet_id}_EHV_fault": faults[1][2],
                        f"j{jet_id}_recovery": faults[1][1],
                        f"j{jet_id}_phase_detection": faults[1][0],
                        f"j{jet_id}_not_present": faults[2][7],
                        f"j{jet_id}_communication_cpu_printer": faults[2][6],
                        f"j{jet_id}_printing_speed_fault": faults[2][5],
                        f"j{jet_id}_DTOP_filtering": faults[2][4],
                        f"j{jet_id}_no_message_to_print": faults[2][3],
                        f"j{jet_id}_incorrect_char_generator_n": faults[2][2],
                        f"j{jet_id}_DTOP_printing": faults[2][1],
                    }
                )

            return True, faults_dict
        else:
            return False, None

    def reset_printer_faults(self) -> int:
        """
        Reset printer faults

        Parameters
        ----------
        None

        Returns
        -------
        return_code : bool
            Returns whether the command was successfully executed or not.

            True = success\n
            False = failure
        """

        return Utils.extract_response_code(
            self.send_command("\\x3C\\x00\\x00\\x3C")
        )
