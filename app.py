from ast import walk
from ctypes import sizeof
import json
import re
import requests
import web

schedules = []

class Schedule:
    sections = []
    score = 0
    flag = False

    def __init__(self, sections):
        self.sections = sections
        self.currrent = 0
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.currrent >= len(self.sections): raise StopIteration
        self.currrent += 1
        return self.sections[self.currrent - 1]
        
    def addSection(self, section):
        self.sections.append(section)

class Section:
    id = ''
    name = ''
    start = 0
    end = 0
    days = ''
    location = ''
    title = ''

    def __init__(self, id, start, end, days, location, name, title):
        self.id = id
        self.start = start
        self.end = end
        self.days = days
        self.location = location
        self.name = name
        self.title = title

# read data.json file and store it
def data():
    with open('data.json', 'r') as f: return json.load(f)

# print schedules from data
def parse_schedules(data):
    for schedule in data['schedules']:
        parsedSchedule = Schedule([])
        for id in schedule['combination']:
            for registrationBlock in data['registrationBlocks']:
                if registrationBlock['id'].replace('`', '') == id:
                    for sectionId in registrationBlock['sectionIds']:
                        for section_raw in data['sections']:
                            if section_raw['id'] == sectionId:
                                start, end, days, location = 0, 0, "", ""
                                for meeting in section_raw['meetings']:
                                    start = meeting['startTime']
                                    end = meeting['endTime']
                                    days = meeting['days']
                                    location = meeting['mapURL']
                                    name = section_raw['subjectId'] + " " + section_raw['course']
                                    title = section_raw['title']
                                section = Section(sectionId, start, end, days, location, name, title)                
                                parsedSchedule.addSection(section)
        schedules.append(parsedSchedule)

# score walk between two coordinates
def time_walk(location1, location2):
    # get approx coords from osm
    coord_data1 = requests.get("http://nominatim.openstreetmap.org/search/?q=" + location1[33:] + "&limit=5&format=json&addressdetails=1").json()
    coord_data2 = requests.get("http://nominatim.openstreetmap.org/search/?q=" + location2[33:] + "&limit=5&format=json&addressdetails=1").json()
    # get distance between two coords from osm
    url = ("https://routing.openstreetmap.de/routed-foot/route/v1/driving/" + coord_data1[0]['lon'] + ',' + coord_data1[0]['lat'] + ';' + coord_data2[0]['lon'] + ',' + coord_data2[0]['lat'])
    route = requests.get(url).json()
    # get time to walk between two coords from  osm
    return route['routes'][0]['duration']

def score_schedule(schedule):
    letters = ['M', 'T', 'W', 'R', 'F']
    # iterate through weekdays
    for letter in letters:
        sections_of_letter = []
        # collect sections within same day
        for section in schedule.sections:
            if letter in section.days: sections_of_letter.append(section)
        
        section1, section2 = Section('', 0, 0, '', '', '', ''), Section('', 0, 0, '', '', '', '')
        # iterate through sections within same day
        while len(sections_of_letter) > 0:
            # find section with earliest start time remaining
            min_section = Section('', 0, 0, '', '', '', '')
            for section in sections_of_letter:
                if min_section.start == 0: min_section = section
                elif section.start < min_section.start: min_section = section

            # fill section1 and section2 sequentially
            # when both sections are filled, calculate walkability and
            # increase score accordingly
            if section1.location == '': section1 = min_section
            elif section2.location == '': 
                section2 = min_section
                time_between = (section2.start - section1.end) # in minutes
                if time_between < 30:
                    walking_time = time_walk(section1.location, section2.location) / 60 # in minutes
                    walkability = walking_time / time_between
                    # assign score increased based on walkability
                    if walkability > 1:     
                        print('Alert: Walking time is greater than time between classes.')
                        schedule.score += 10
                        schedule.flag = True
                    elif walkability > (2/3): schedule.score += 3
                    elif walkability > (1/2): schedule.score += 1
                # print("Time Between: " + str((section2.start - section1.end)) + " minutes\n")
                # clear section1 and section2 after calculating walkability
                section1, section2 = Section('', 0, 0, '', '', '', ''), Section('', 0, 0, '', '', '', '')
            sections_of_letter.remove(min_section)

    print('Score: ' + str(schedule.score))
    return

# read json to object
def toJSON(self):
    return json.dumps(self, default=lambda o: o.__dict__, 
        sort_keys=True, indent=4)


# save schedules to json file
def save_schedules():
    with open('static/schedules.json', 'w') as f:
        f.write(toJSON(schedules))

# process data from schedulebuilder
def process_data(data):
    parse_schedules(data)
    index = 1
    for schedule in schedules:
        print('\nProcessing schedule: ' + str(index))
        score_schedule(schedule)
        save_schedules()
        index += 1
    save_schedules()

data = data()

# web server
urls = (
    '/(.*)', 'home',
)
app = web.application(urls, globals())

class home:
    def GET(self, name):
        regex = re.compile('schedules/.')
        if re.match(regex, name) != None:
            with open('static/schedules.json', 'r') as file: 
                render = web.template.render('templates/')
                return str(render.process_schedules()) + file.read()
                
        return "Hello, world!"
    
    def POST(self, name):
        # process data
        process_data(data)
        # read new data and return
        with open('static/schedules.json', 'r') as file: 
                render = web.template.render('templates/')
                return str(render.process_schedules()) + file.read()

if __name__ == "__main__":
    app.run()