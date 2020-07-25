# restworklist plugin for Orthanc DICOM server
# creates DICOM worklist files in the WorklistDir which may be used by SampleModalityWorklist plugin lateron
import json, sqlite3
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom import dcmread
from PIL import Image
import pydicom
import orthanc
import os
import io
import re
import threading
import multiprocessing
import signal
import codecs
import urllib.request
from datetime import datetime
from collections import defaultdict

def Initializer():
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
sexReplacement = { '0': 'O', '1': 'M', '2': 'F', '3': 'O' }
TIMER = None

class SqliteContainer:
    def __init__(self, db):
        self.conn = sqlite3.connect(db)
        
    def __del__(self):
        self.conn.close()

orthancConfig = json.loads(orthanc.GetConfiguration())
if 'GdtGenerator' in orthancConfig and orthancConfig['GdtGenerator']['Enable']:
    sqliteContainer = SqliteContainer(orthancConfig["GdtGenerator"]["TransmittedStudiesDatabase"])
    cur = sqliteContainer.conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS transmitted_studies (uuid TEXT PRIMARY KEY NOT NULL)");
    sqliteContainer.conn.commit()
    del cur

def gdtResponse(patid, date, uid, modality):
    template = "{length:03d}{typ:04d}{content}\r\n"

    testid = "EXTPACS"
    testdesc = "PACS-Datensatz"

    try:
        testid = orthancConfig['GdtGenerator']['TestId']
        testdesc = orthancConfig['GdtGenerator']['TestDescription']
    except KeyError:
        pass

    lines = []
    lines.append((8000, "6310"))
    lines.append((8002, "Obj_Kopfdaten"))
    lines.append((8315, "PRAX_EDV"))
    lines.append((8316, "ORTHANC"))
    lines.append((9218, "03.1"))
    lines.append((8003, "Obj_Kopfdaten"))
    lines.append((8002, "Obj_Patient"))
    lines.append((3000, patid))
    lines.append((8003, "Obj_Patient"))
    lines.append((8002, "Obj_Untersuchung"))
    lines.append((8410, testid))
    lines.append((8411, testdesc))
    lines.append((8413, uid))
    lines.append((8428, uid))
    lines.append((8432, date.strftime("%d%m%Y")))
    lines.append((8439, date.strftime("%H%M%S")))
    lines.append((6228, "{} / {}".format(uid, modality)))
    lines.append((8003, "Obj_Untersuchung"))
    lines.append((8001, "6310"))
    
    result = ''.join([ template.format(length = 9 + len(line[1]), typ = line[0], content = line[1]) for line in lines ])
    return result.encode('iso-8859-15')


def OnRest(output, uri, **request):
    config = orthancConfig
    try:
        worklistdir = config["Worklists"]["Database"]
        asnofile = os.sep.join([worklistdir, 'accessionid.conf'])
    except KeyError:
        output.AnswerBuffer('internal configuration error\n', 'text/plain')
        return
    
    try:
        today = datetime.today()
        
        try:
            with open(asnofile, 'r') as f:
                try:
                    asno = int(f.read())
                except ValueError:
                    asno = 1
        except OSError:
            asno = 1
        
        with open(asnofile, 'w') as f:
            f.write(str(asno+1))
        
        # File meta info data elements
        file_meta = FileMetaDataset()
        file_meta.FileMetaInformationGroupLength = 202
        file_meta.FileMetaInformationVersion = b'\x00\x01'
        file_meta.MediaStorageSOPClassUID = '1.2.276.0.7230010.3.1.0.1'
        file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid(prefix = None)
        file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
        file_meta.ImplementationClassUID = '1.2.276.0.7230010.3.0.1.0.0'
        file_meta.ImplementationVersionName = 'ORTHANC_RESTWORKLIST_1'

        # Main data elements
        ds = Dataset()
        ds.SpecificCharacterSet = 'ISO_IR 192'
        
        dcm_store_path = os.sep.join([worklistdir, 'R{:010d}-{}.{}'.format(asno, today.strftime('%Y%m%d%H%M%S'), 'wl')])
        ds.AccessionNumber = 'R{:010d}'.format(asno)
        try:
            ds.PatientName = '{}^{}'.format(request["get"]["lastname"], request["get"]["firstname"])
        except KeyError:
            ds.PatientName = '{}^{}'.format(request["get"]["name"], request["get"]["surname"]) # old, buggy parameter naming -> for backwards compatibility
        ds.PatientID = request["get"]["id"]
        bdparts = request["get"]["birthdate"].split('.')
        ds.PatientBirthDate = '{2}{1}{0}'.format(*bdparts)
        ds.PatientSex = sexReplacement[request["get"]["sex"]] # LUT for the sex identifier numbers used by Medical Office (0 = Other / Unknown, 1 = Male, 2 = Female, 3 = Other / Unknown)
        ds.StudyInstanceUID = pydicom.uid.generate_uid(prefix = None)
        try:
            ds.RequestedProcedureDescription = request["get"]["procedure"]
        except KeyError:
            pass # optional argument, otherwise this tag remains empty

        # Scheduled Procedure Step Sequence
        scheduled_procedure_step_sequence = Sequence()
        ds.ScheduledProcedureStepSequence = scheduled_procedure_step_sequence

        # Scheduled Procedure Step Sequence: Scheduled Procedure Step 1
        scheduled_procedure_step1 = Dataset()
        try:
            scheduled_procedure_step1.Modality = request["get"]["modality"]
        except KeyError:
            scheduled_procedure_step1.Modality = 'US' # fallback to default (backwards compatibility)
            
        try:
            scheduled_procedure_step1.ScheduledStationAETitle = request["get"]["scheduledStation"]
        except KeyError:
            scheduled_procedure_step1.ScheduledStationAETitle = 'US01' # fallback to default (backwards compatibility)
            
        scheduled_procedure_step1.ScheduledProcedureStepStartDate = today.strftime('%Y%m%d')
        scheduled_procedure_step1.ScheduledProcedureStepStartTime = today.strftime('%H%M%S')
        
        try:
            scheduled_procedure_step1.ScheduledPerformingPhysicianName = request["get"]["physician"]
        except KeyError:
            pass # optional, leave empty if not specified
        
        scheduled_procedure_step_sequence.append(scheduled_procedure_step1)

        ds.file_meta = file_meta
        ds.is_implicit_VR = False
        ds.is_little_endian = True
        ds.save_as(dcm_store_path, write_like_original=False)
        output.AnswerBuffer(gdtResponse(request["get"]["id"], today, ds.AccessionNumber, request["get"]["procedure"]), 'text/plain')
        
        if "UrlOnWorklistEntryAdded" in config["Worklists"]:
            with urllib.request.urlopen(config["Worklists"]["UrlOnWorklistEntryAdded"]):
                    orthanc.LogWarning("Called {} as configured.".format(config["Worklists"]["UrlOnWorklistEntryAdded"]))
    except KeyError as e:
        output.AnswerBuffer('error: {}\n'.format(e), 'text/plain')
        raise

def parseSRContent(nodeContainer, level = 0, ultraSoundParams = defaultdict(list)):
    nodeValueMap = defaultdict(list)
    for node in nodeContainer:
        ns = node["ConceptNameCodeSequence"][0]
        if node["ValueType"] == 'TEXT':
            nodeValueMap[ns["CodeValue"]].append(node["TextValue"])
        elif node["ValueType"] == 'NUM':
            mvs = node["MeasuredValueSequence"][0]
            mucs = mvs["MeasurementUnitsCodeSequence"][0]
            nodeValueMap[ns["CodeValue"]].append({ 'value': mvs["NumericValue"], 'unit': mucs["CodeValue"], 'meaning': ns["CodeMeaning"] })
        elif node["ValueType"] == 'CODE':
            ccs = node["ConceptCodeSequence"][0]
            nodeValueMap[ns["CodeValue"]].append({'code': ccs["CodeValue"], 'meaning': ccs["CodeMeaning"]})
        elif node["ValueType"] == 'CONTAINER':
            result, ultraSoundParams = parseSRContent(node["ContentSequence"], level + 1, ultraSoundParams = ultraSoundParams)
            if ns["CodeValue"] == '10020':
                usobj = {
                    'id': result['10033'][0],
                    'realid': result['10031'][0],
                    'displayName': 'US ' + result['10033'][0],
                    'valueSource': result['10036'][0],
                    'resultNumber': result['10037'][0],
                    'value': result['10041'][0],
                    'displayUnit': result['10042'][0],
                    'manuallyEdited': result['10043'][0]
                }
                nodeValueMap[ns["CodeValue"]].append(usobj)
                ultraSoundParams[usobj['id']].append(usobj)
            elif ns["CodeValue"] == '125007':
                try:
                    valueSource = result['G-0373'][0]['meaning']
                except KeyError:
                    valueSource = 'X'
                for code, pitem in result.items():
                    if code != 'G-0373':
                        for item in pitem:
                            if float(item["value"]) > -1:
                                parts = item['meaning'].split(' ')
                                keypart = ['EC', valueSource[:2]]
                                keypart.extend([p[0] for p in parts])
                                pid = ''.join(keypart)
                                usobj = {
                                    'id': pid,
                                    'displayName': '{meaning} ({source})'.format(meaning = item['meaning'], source= valueSource),
                                    'value': item,
                                    'displayUnit': item['unit'],
                                    'manuallyEdited': '0',
                                    'valueSource': valueSource,
                                    'resultNumber': '-1'
                                }
                                #for k in ultraSoundParams[usobj['id']]:
                                #    print(k['valueSource'])
                                
                                ultraSoundParams[usobj['id']] = [ k for k in ultraSoundParams[usobj['id']] if k['valueSource'] != valueSource ]
                                ultraSoundParams[usobj['id']] = [usobj]
    
    return (nodeValueMap, ultraSoundParams)

def ConvertColorspace(dicom):
    ds = dcmread(io.BytesIO(dicom))
    quality = 90
    if ds.SOPClassUID == "1.2.840.10008.5.1.4.1.1.3.1":
        quality = 75
    frames = []
    frame_generator = pydicom.encaps.generate_pixel_data_frame(ds.PixelData, ds.NumberOfFrames)
    print("Transcoding image with {:d} frames".format(ds.NumberOfFrames))
    
    for frame in frame_generator:
        with io.BytesIO(frame) as ins:
            img = Image.open(ins)
            img.convert('YCbCr')
            with io.BytesIO() as output:
                img.save(output, 'jpeg', optimize = True, quality = 75)
                frames.append(output.getvalue())
    
    ds.PhotometricInterpretation = 'YBR_FULL'
    ds.PixelData = pydicom.encaps.encapsulate(frames)
    #ds.file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.4.50'
    #ds.file_meta.
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    with io.BytesIO() as out:
        ds.save_as(out)
        contents = out.getvalue()
    
    return contents
    
def OnStoredInstance(dicom, instanceId):
    instanceTags = json.loads(dicom.GetInstanceSimplifiedJson())
    
    if dicom.GetInstanceOrigin() == orthanc.InstanceOrigin.DICOM_PROTOCOL and ((instanceTags["SOPClassUID"] == "1.2.840.10008.5.1.4.1.1.3.1" or instanceTags["SOPClassUID"] == "1.2.840.10008.5.1.4.1.1.6.1") 
        and instanceTags["ImageType"] == "DERIVED\\PRIMARY" and instanceTags["Manufacturer"] == "Sonoscape"):
        instData = dicom.SerializeDicomInstance()
        answer = POOL.apply(ConvertColorspace, args = (instData,))
        orthanc.RestApiPost('/instances', answer)
        orthanc.RestApiDelete('/instances/{}'.format(instanceId))
    elif dicom.GetInstanceOrigin() == orthanc.InstanceOrigin.DICOM_PROTOCOL and instanceTags["Manufacturer"] == "Sonoscape" and instanceTags["Modality"] == "SR":
        instData = dicom.SerializeDicomInstance()
        ds = dcmread(io.BytesIO(instData))
        ds.SeriesInstanceUID = '.'.join([ds.StudyInstanceUID, '1'])
        ds.SOPInstanceUID = pydicom.uid.generate_uid()
        ds.SeriesNumber = str(int(ds.SeriesNumber) + 1)
        ds.SeriesDescription = "Structured Reports"
        with io.BytesIO() as out:
            ds.save_as(out)
            orthanc.RestApiPost('/instances', out.getvalue())
        orthanc.RestApiDelete('/instances/{}'.format(instanceId))
    else:
        try:
            config = orthancConfig["GdtGenerator"]
        except KeyError:
            return
        
        if not config["Enable"]:
            return
        try:
            incomingdir = config["IncomingDir"]
            dbfile = config["TransmittedStudiesDatabase"]
        except KeyError:
            orthanc.LogError("IncomingDir or TransmittedStudiesDatabase is not set in Configuration:GdtGenerator")
            return
        
        sqliteContainer = SqliteContainer(dbfile)
        cur = sqliteContainer.conn.cursor()
        
        instance = json.loads(orthanc.RestApiGet('/instances/{}'.format(instanceId)))
        
        studyTime = instanceTags["StudyTime"]
        studyDate = instanceTags["StudyDate"]
        series = json.loads(orthanc.RestApiGet('/series/{}'.format(instance["ParentSeries"])))
        studyUid = series["ParentStudy"]
        if instanceTags["SOPClassUID"] == "1.2.840.10008.5.1.4.1.1.88.33":
            templateId = instanceTags["ContentTemplateSequence"][0]["TemplateIdentifier"]
            if templateId == "SONO1000" or templateId == "5200":
                
                year = int(studyDate[0:4])
                month = int(studyDate[4:6])
                day = int(studyDate[6:8])
                hour = 0
                minute = 0
                second = 0
                msecond = 0
                
                studyTimeLen = len(studyTime)
                if studyTimeLen >= 2:
                    hour = int(studyTime[0:2])
                if studyTimeLen >= 4:
                    minute = int(studyTime[2:4])
                if studyTimeLen >= 6:
                    second = int(studyTime[4:6])
                if studyTimeLen > 7 and studyTime[6] == '.':
                    msecond = int(studyTime[7:])
                    
                studyDatetime = datetime(year, month, day, hour = hour, minute = minute, second = second, microsecond = msecond)
                patientID = instanceTags["PatientID"]
                
                ultrasoundParams = defaultdict(list)
                _, ultrasoundParams = parseSRContent(instanceTags["ContentSequence"], ultraSoundParams = ultrasoundParams)
                
                gdtlines = []
                gdtlines.append((8000, "6310"))
                gdtlines.append((8315, "MEDOFF"))
                gdtlines.append((8316, "ORTHANC"))
                gdtlines.append((9218, "01.0"))
                gdtlines.append((3000, instanceTags["PatientID"]))
                gdtlines.append((6200, studyDatetime.strftime("%d%m%Y")))
                pattern = re.compile('[\W_]+')
                for pid, params in ultrasoundParams.items():
                    for param in params:
                        if int(param["resultNumber"]) == -1:
                            try:
                                val = float(param["value"]["value"])
                                dn = ("So" + pattern.sub('', param["id"]))
                                gdtlines.append((8410, dn.upper()))
                                gdtlines.append((8411, param["displayName"]))
                                gdtlines.append((8420, str(val)))
                                gdtlines.append((8421, param["displayUnit"]))
                                gdtlines.append((8432, studyDatetime.strftime('%d%m%Y')))
                                gdtlines.append((8439, studyDatetime.strftime('%H%M%S')))
                                if 'realid' in param:
                                    gdtlines.append((8470, 'Id: ' + param['realid']))
                                gdtlines.append((8470, 'Quelle: ' + param["valueSource"]))
                            except ValueError:
                                pass
                
                gdtlines.append((8001, "6310"))
                template = "{length:03d}{typ:04d}{content}\r\n"
                result = ''.join([ template.format(length = 9 + len(line[1]), typ = line[0], content = line[1]) for line in gdtlines ])
                
                accessionNumber = instanceTags["AccessionNumber"]
                gdtfile = os.path.join(incomingdir, '{}-sr-{}.gdt'.format(accessionNumber, instanceTags["SOPInstanceUID"]))
                
                with codecs.open(gdtfile, encoding="iso-8859-15", mode="w") as f:
                    f.write(result)
                orthanc.LogWarning("GDT file {} generated.".format(gdtfile))
        else:
            try:
                cur.execute("INSERT INTO transmitted_studies VALUES (?)", (studyUid,))
                sqliteContainer.conn.commit()
                                        
                year = int(studyDate[0:4])
                month = int(studyDate[4:6])
                day = int(studyDate[6:8])
                hour = 0
                minute = 0
                second = 0
                msecond = 0
                
                studyTimeLen = len(studyTime)
                if studyTimeLen >= 2:
                    hour = int(studyTime[0:2])
                if studyTimeLen >= 4:
                    minute = int(studyTime[2:4])
                if studyTimeLen >= 6:
                    second = int(studyTime[4:6])
                if studyTimeLen > 7 and studyTime[6] == '.':
                    msecond = int(studyTime[7:])
                    
                studyDatetime = datetime(year, month, day, hour = hour, minute = minute, second = second, microsecond = msecond)
                accessionNumber = instanceTags["AccessionNumber"]
                description = '{modality}: {description}'.format(modality = instanceTags["Modality"], description = instanceTags["StudyDescription"])
                patientID = instanceTags["PatientID"]
                
                gdtfile = os.path.join(incomingdir, '{}.gdt'.format(accessionNumber))
                with open(gdtfile, "wb") as f:
                    f.write(gdtResponse(patientID, studyDatetime, accessionNumber, description))
                orthanc.LogWarning("GDT file {} generated.".format(gdtfile))
                
                if "UrlOnGdtWritten" in config:
                    with urllib.request.urlopen(config["UrlOnGdtWritten"]):
                        orthanc.LogWarning("Called {} as configured.".format(config["UrlOnGdtWritten"]))
            except sqlite3.Error as e:
                pass
        

def CleanupWorklist():
    global TIMER
    TIMER = None
        
    try:
        wlDir = orthancConfig["Worklists"]["Database"]
        interval = orthancConfig["Worklists"]["CleanupInterval"]
    except KeyError:
        interval = None
        
    if interval is not None:
        orthanc.LogWarning("Cleaning up worklist files...")
        wlFiles = [ f for f in os.listdir(wlDir) if os.path.isfile(os.path.join(wlDir, f)) and f.endswith('.wl') ]

        today = datetime.today()

        for wlFile in wlFiles:
            unlink = False
            filename, _ = os.path.splitext(wlFile)
            accessionId, dateVal = filename.split('-', 1)
            dt = datetime.strptime(dateVal, '%Y%m%d%H%M%S')
            
            if dt.date() < today.date():
                unlink = True
            else:
                try:
                    study = orthanc.LookupStudyWithAccessionNumber(accessionId)
                    if study is not None:
                        unlink = True
                except ValueError:
                    pass
                    
            if unlink:
                os.unlink(os.path.join(wlDir, wlFile))
            
        TIMER = threading.Timer(interval, CleanupWorklist)
        TIMER.start()

def OnChange(changeType, level, resource):
    if changeType == orthanc.ChangeType.ORTHANC_STARTED:
        CleanupWorklist()
    elif changeType == orthanc.ChangeType.ORTHANC_STOPPED:
        if TIMER != None:
            TIMER.cancel()

orthanc.RegisterRestCallback('/worklist/add', OnRest)
orthanc.RegisterOnStoredInstanceCallback(OnStoredInstance)
orthanc.RegisterOnChangeCallback(OnChange)

POOL = multiprocessing.Pool(4, initializer = Initializer)
