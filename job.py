class Job:

    def __init__(self, input_string):
        # '1,1,4,1,1,1,1,0,0,0,0,0,0,queued'
        parsed_params = input_string.split(',')
        self.serial = parsed_params[0]
        self.instrument = parsed_params[1]
        self.ball_count = parsed_params[2]
        self.ball_1 = parsed_params[3]
        self.ball_2 = parsed_params[4]
        self.ball_3 = parsed_params[5]
        self.ball_4 = parsed_params[6]
        self.attr_count = parsed_params[7]
        self.attr_1 = parsed_params[8]
        self.attr_2 = parsed_params[9]
        self.attr_3 = parsed_params[10]
        self.attr_4 = parsed_params[11]
        self.seconds_done = parsed_params[12]
        self.status = parsed_params[13]
    def str(self):
        return self.__str__()
    def __str__(self):
        return f"S:{self.serial} I:{self.instrument} {self.status} {self.seconds_done}s B:{self.ball_1}{self.ball_2}{self.ball_3}{self.ball_4} A:{self.attr_1}{self.attr_2}{self.attr_3}{self.attr_4}"
    
