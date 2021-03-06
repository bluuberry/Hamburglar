import re
import os
import sys
import threading
import json
from urllib.request import urlopen
import argparse

#if(len(sys.argv) != 2):
#    print("[-] Argument Error: Use hamburglar.py </path/to/file/or/directory>")
#    exit()


whitelistOn= False #Set True to filter by whitelist

maxWorkers= 20 #Max workers for reading and sniffing each file

whitelist= [".txt",".html",".md"] # Add to whitelist to ONLY sniff certain files or directories


# Add to blacklist to block files and directories
blacklist = [
    ".git/objects/",
    ".git/index",
    "/node_modules/",
    "vendor/gems/",
    ".iso",
    ".bundle",
    ".png",
    ".jpg",
    ".crt",
    ".exe",
    ".gif",
    ".mp4",
    ".mp3"
]

# Regex dictionary, comment out a line to stop checking for entry, and add a line for new filters
regexList= {
    "AWS API Key": "AKIA[0-9A-Z]{16}",
#    "bitcoin-address" : "[13][a-km-zA-HJ-NP-Z1-9]{25,34}" ,
    "bitcoin-cash-address":"(?:^[13][a-km-zA-HJ-NP-Z1-9]{33})",
    "bitcoin-uri" : "bitcoin:([13][a-km-zA-HJ-NP-Z1-9]{25,34})" ,
    "bitcoin-xpub-key" : "(xpub[a-km-zA-HJ-NP-Z1-9]{100,108})(\\?c=\\d*&h=bip\\d{2,3})?" ,
    "dash-address":"(?:^X[1-9A-HJ-NP-Za-km-z]{33})",
    "dogecoin-address":"(?:^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32})",
    "email":"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+",
    "ethereum-address": "(?:^0x[a-fA-F0-9]{40})",
    "Facebook Oauth": "[f|F][a|A][c|C][e|E][b|B][o|O][o|O][k|K].*['|\"][0-9a-f]{32}['|\"]",
    "Generic Secret": "[s|S][e|E][c|C][r|R][e|E][t|T].*['|\"][0-9a-zA-Z]{32,45}['|\"]",
    "GitHub": "[g|G][i|I][t|T][h|H][u|U][b|B].*[['|\"]0-9a-zA-Z]{35,40}['|\"]",
    "Google Oauth": "(\"client_secret\":\"[a-zA-Z0-9-_]{24}\")",
    "Heroku API Key": "[h|H][e|E][r|R][o|O][k|K][u|U].*[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}",
    "ipv4":"[0-9]+(?:\.[0-9]+){3}",
    "litecoin-address":"(?:^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33})",
    "monero-address": "(?:^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93})",
    "neo-address":"(?:^A[0-9a-zA-Z]{33})",
    "PGP private key block": "-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "phone":"^(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}$",
    "ripple-address":"(?:^r[0-9a-zA-Z]{33})",
    "RSA private key": "-----BEGIN RSA PRIVATE KEY-----",
    "site":"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+",
    "Slack Token": "(xox[p|b|o|a]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32})",
    "SSH (DSA) private key": "-----BEGIN DSA PRIVATE KEY-----",
    "SSH (EC) private key": "-----BEGIN EC PRIVATE KEY-----",
    "SSH (OPENSSH) private key": "-----BEGIN OPENSSH PRIVATE KEY-----",
    "Twitter Oauth": "[t|T][w|W][i|I][t|T][t|T][e|E][r|R].*['|\"][0-9a-zA-Z]{35,44}['|\"]"
}


parser = argparse.ArgumentParser()

parser.add_argument("-v", "--verbose", help="increase output verbosity",
                    action="store_true")

parser.add_argument("-w","--web", help="sets Hamburgler to web request mode, enter url as path",
                    action="store_true")

parser.add_argument("path",help="path to directory, url, or file, depending on flag used")
args= parser.parse_args()

#Get Path Argument (file url or directory)
passedPath = args.path


#only use unique filepaths(should be unique anyways, just redundant)
filestack= set()
requestStack= set()

cumulativeFindings= {}

def webScan():
    """ Scans the url given in the path, then adds to request stack (eventually this may be a spider """
    requestStack.add(passedPath)

def scan():
    """ scans the directory for files and adds them to the filestack """
    # check for directory
    if(os.path.isfile(passedPath)==False):

        for root, subFolders, files in os.walk(passedPath):     #iterate through every file in given directory
            for entry in files:     #get all files from root directory

                filepath= os.path.join(root,entry)

                if(whitelistOn):
                    #if whitelisted, check if entry is valid and add to stack
                    if _iswhitelisted(filepath):
                        print("[+] whitelist finding: "+str(filepath))
                        filestack.add(filepath)
                    else:
                        #if its not, forget about the file
                        break
                elif _isfiltered(filepath):
                    #if whitelist is off, check blacklist
                            if(args.verbose): print("[-] "+filepath+" blacklisted, not scanning")
                            break
                else:
                    #lastly, if it is not blacklisted, lets add the file to the stack
                    try:
                        print("[+] adding:"+str(filepath)+" ("+str(os.stat(filepath).st_size >> 10)+"kb) to stack")
                        filestack.add(filepath)
                    except Exception as e:
                        print("[-] read error: "+str(e) )

            for folder in subFolders: # check every subFolder recursively
                for entry in files:
                    filepath= os.path.join(root,entry)
                    if whitelistOn:
                        #if whitelisted, check if entry is valid and add to stack
                        if _iswhitelisted(filepath):
                            print("[+] whitelist finding: "+str(filepath))
                            filestack.add(filepath)
                        else:#if its not, forget about the file
                            break
                    elif _isfiltered(filepath):
                        #if whitelist is off, check blacklist
                                if(args.verbose): print("[-] "+filepath+" blacklisted, not scanning")
                                break
                    else:
                        #lastly, if it is not blacklisted, lets add the file to the stack
                        try:
                            print("[+] adding:"+str(filepath)+" ("+str(os.stat(filepath).st_size >> 10)+"kb) to stack")
                            filestack.add(filepath)
                        except Exception as e:
                            print("[-] read error: "+str(e) )

    else:
        #we just have a single file, so add it to the stack
        print("[+] single file passed")
        filestack.add(passedPath)

def _isfiltered(filepath):
    """ checks if the file is blacklisted """
    for filtered in blacklist:
        if (filtered in filepath): return True
    return False

def _iswhitelisted(filepath):
    """ checks if the file given is whitelisted """
    for filtered in whitelist:
        if (filtered in filepath): return True
    return False

def _url_read():
    """ opens the urls in requestStack, makes request, and if something matchest the regex, add it to the cumulativeFindings """

    while(requestStack): # while there are still requests to be made
        url=requestStack.pop()
        if(args.verbose):print("[+] left on stack: "+str(len(requestStack)))

        try:
            with urlopen(url) as response:
                html = response.read()
                data= str(html).rstrip("\r\n")
                results= _sniff_text(data)

                if(len(results.items())>0):
                    totalResults=sum(map(len, results.values()))
                    print("[+] "+url+" -- "+str(totalResults)+" result(s) found.")
                    cumulativeFindings.update({url:results})

        except Exception as e:
            print("Url Worker Error: "+str(e))


def _file_read():
    """ opens the files in filestack, reads them , and if something is found in the file that matches the regex, adds them to cumalativeFindings"""
    while(filestack): #while there are still items on the stack/worker pool...
        filepath= filestack.pop()
        if(args.verbose): print("[+] left on stack: "+str(len(filestack)))
        try:
            with open(filepath, "r") as scanfile: #open file on stack that needs sniffed

                filestring = str(scanfile.read()).rstrip('\r\n') # turn file to string and clean it of newlines
                results = _sniff_text(filestring) #get dictionary of results from regex search

                if (len(results.items())>0): # if we found something in the file, add it to the findings report
                    totalResults=len(results.items())
                    print("[+] "+filepath+" -- "+str(totalResults)+" result(s) found.")
                    cumulativeFindings.update({filepath:results})

        except Exception as e:
            print("[-] "+filepath+": can't be read: "+str(e))


def _sniff_text(text):
    """ checks every regex for findings, and return a dictionary of all findings """
    results= {}
    for key, value in regexList.items():
        findings= set(re.findall(value, text))
        if findings:
            results.update({key:findings})
    return results

def displayCumulative():
    """ Displays finding report """
    print(json.dumps(dict(cumulativeFindings), default=lambda x: str(x), sort_keys=True, indent=4))

def _write_to_file():
    """ writes report to json file """
    with open('hamburglar-results.json', 'w') as file:
        file.write(json.dumps(dict(cumulativeFindings), default=lambda x: str(x), sort_keys=True, indent=4))


if __name__ == "__main__":
    print("[+] scanning...")
    if(args.web):
        webScan()
    else:
        scan()
    print("[+] scan complete")


    workerType = _url_read if args.web else _file_read #set scantype based of url or directory/file traverseal

    workers= [] # workers to handle filestack
    for x in range(maxWorkers):#start up file reading worker threads
        t=threading.Thread(target=workerType)
        t.start()
        workers.append(t)

    for worker in workers:# join all workers to conclude scan
        worker.join()

    print("[+] writing to hamburglar-results.json...")
    _write_to_file()
    print("[+] The Hamburglar has finished snooping")
