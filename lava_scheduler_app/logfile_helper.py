import re

def getDispatcherErrors(logfile):
    errors = ""
    for line in logfile:
        if line.find("CriticalError:") != -1 or \
           line.find("Lava failed on test:") != -1 :
            errors += line

    return errors

def getDispatcherLogMessages(logfile):
    logs = []
    log_prefix = '<LAVA_DISPATCHER>'
    level_pattern = re.compile('....-..-.. ..:..:.. .. ([A-Z]+):')
    for line in logfile:
        if not line.startswith(log_prefix):
            continue
        line = line[len(log_prefix):].strip()
        match = level_pattern.match(line)
        if not match:
            continue
        if len(line) > 90:
            line = line[:90] + '...'
        logs.append((match.group(1), line))
    return logs

class Sections:
    def __init__(self):
        self.sections = []
        self.cur_section_type = None
        self.cur_section = []
    def push(self, type, line):
        if type != self.cur_section_type:
            self.close()
            self.cur_section_type = type
        self.cur_section.append(line)
    def close(self):
        if self.cur_section_type is not None:
            self.sections.append(
                (self.cur_section_type,
                 len(self.cur_section),
                 ''.join(self.cur_section)))
        self.cur_section_type = None
        self.cur_section = []

def formatLogFile(logfile):
    if not logfile:
        return [('log', 1, "Log file is missing")]

    sections = Sections()

    for line in logfile:
        line = line.replace('\r', '')
        if not line:
            continue
        if line == 'Traceback (most recent call last):\n':
            sections.push('traceback', line)
        elif sections.cur_section_type == 'traceback':
            sections.push('traceback', line)
            if not line.startswith(' '):
                sections.close()
            continue
        elif line.find("<LAVA_DISPATCHER>") != -1 or \
                 line.find("lava_dispatcher") != -1 or \
                 line.find("CriticalError:") != -1 :
            sections.push('log', line)
        else:
            sections.push('console', line)
    sections.close()

    return sections.sections
