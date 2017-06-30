#!/usr/bin/env python
"""
ab spider, proof-of-concept. If you are interested in the software, get in touch.

@author: Andres Baravalle
"""

# change getUrl to add sanity checks in each URL that is requested
# check if the proxy (tor) is refusing a connection
# set command line options (db missing)
# check yeld in python
# check credit available for captchas
# refresh tor IP each time it runs
# problems around log file. Might be worth just saving on db?
# detect flood limit message immediately
# run a thread that checks for the login window when loading a URL and/or timeouts
# move the vars from the pickle to the db
# review the captcha functions
# should we check the login page by URL?

# save the position of the last category spidered and restart from there
# rewrite the category part of the scripts, to link a name to a category id too
# download image and upload on s3 or similar
# refactor to make object oriented
# should pick also the number of sold items, and save in a different table with progression
# support multiple configuration files
# check if the combination of product and category has been saved; 
# if the product is in the db, check against the current category
# check the categories from which we have downloaded products
# rewrite with automatic restart after one hour
# freshen links after some days?

# os should be first
import os
import argparse
import base64
import boto3
import datetime
import hashlib
# import logger
import io
import logging
# using mysqlclient
import MySQLdb
import names
import pickle
import random
import re
import socket
import sys
import string
import subprocess
import shlex
import urllib
from datetime import datetime
# using Pillow
from PIL import Image
from random import shuffle
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC
from pprint import pprint
from settings_uni import *
# from settings_laptop import *
import tempfile
import time
# this should be moved somewhere else - shouldn't be in the main class
from twocaptchaapi import TwoCaptchaApi

__version__ = '0.0.1'


# will include the categories with products

def checkSettings():
    # This function will check all the settings, before the software starts
    global categories, logger, db_products, savedVars
    
    tmp_return = True

    # let's set the logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    # create a file handler
    handler = logging.FileHandler(logfile)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    if os.path.isdir(project_home):
        logger.debug("Test passed: project home.")
        os.chdir(project_home)
    else:
        tmp_return = False
    if os.path.isdir(tor["profile_folder"]):
        logger.debug("Test passed: Tor profile home.")
    else:
        tmp_return = False
        
    if os.path.isfile(tor["cmd"]):
        logger.debug("Test passed: tor binary.")
    else:
        tmp_return = False
         
    if os.path.isfile(gecko_binary):
        logger.debug("Test passed: gecko binary.")
    else:
        tmp_return = False        
         
    # let's check if tor is already running in the target port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.bind(("127.0.0.1", tor["socks_port"]))
    except socket.error as e:
        logger.info("Something is already running in port {}. I'll assume it's tor.".format(tor["socks_port"]))
    else:
        # starts tor from the command line
        tor_args = r' --SocksPort {} --ControlPort {}'.format(tor["socks_port"], tor["control_port"])
        torprocess = subprocess.Popen([tor["cmd"]] + shlex.split(tor_args))
        if torprocess:
            logger.debug("The pid for the current tor proxy is: " + str(torprocess.pid))
    
    s.close()     
    
    if not dbConnect(): 
        tmp_return = False
    else:
    # should check if logged in   
    # let's find the list of all products, ids only
        db_products = dbGetProducts()
        
        if db_products:
            # if there are no products in a while we should kill the script
            logger.info("{0} products in db".format(len(db_products)))
            
            savedVars = getVars()
            categories = savedVars['categories']
            logger.info("Total n of categories: " + str(len(categories)))
            
        else:
            tmp_return = False
    
    return tmp_return
# tor_profile_folder

def setOptions():
    # setting global variables
    global project_home, tor, gecko_binary, alphauser, alphapsw, db_connection
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_home", help="Set the project home in the local filesystem.")
    parser.add_argument("--tor_profile_folder", help="Set the profile folder for Tor.")
    parser.add_argument("--gecko_binary", help="Set the location for the gecko binary.")
    parser.add_argument("--verbosity", help="Set the level of verbosity.")
    parser.add_argument("--alphauser", help="Set the site username")
    parser.add_argument("--alphapsw", help="Set the site password")
    parser.add_argument("--db", help="Set the connection string for the db")
    parser.add_argument("--tor_cmd", help="Set the location for the Tor binary")
    parser.add_argument("--tor_profile_folder", help="Set the Tor profile folder")
    parser.add_argument("--tor_socks_port", help="Set the Tor socks port")
    parser.add_argument("--tor_control_port", help="Set the Tor control port")

    # let's check if there are any args
    
    args = parser.parse_args()
    if args.verbosity:
        print("Verbosity turned on")

    # let's check the folders
    if args.project_home:
        project_home = args.project_home

    if args.gecko_binary:
        gecko_binary = args.gecko_binary
    if args.alphauser:
        alphauser = args.alphauser
    if args.alphapsw:
        alphapsw = args.alphapsw
    if args.db:
        db = args.db
        # need to expand on this, extracting the different parts
    if args.tor_cmd:
        tor["cmd"] = args.tor_cmd
    if args.tor_profile_folder:
        tor["profile_folder"] = args.tor_profile_folder
    if args.tor_socks_port:
        tor["socks_port"] = args.tor_socks_port
    if args.control_port:
        tor["control_port"] = args.tor_control_port
    
def newUser():
    # This function create a new user that will be used during the spidering session.

    getUrl(site_new_user)
    
    if saveCaptcha():   
    
        # let's start by generating a new username
        username = names.get_full_name().replace(" ", "")
        password = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for x in range(12))
        pin = ''.join(random.SystemRandom().choice(string.digits) for x in range(6))

        try:
                # <input name="user" class="std" size="65" value="" type="text">
                usernameElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="da_username"]')
                pwdElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="da_passwd"]')
                pwdElement2 = alphaspider.find_element_by_xpath('//input[@class="std" and @name="da_passcf"]')
                pinElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="da_pin"]')
                captchaElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="captcha_code"]')
                submitElement = alphaspider.find_element_by_xpath('//input[@class="bstd" and @value="Join the market"]')
        
                usernameElement.click()
                usernameElement.clear()
                usernameElement.send_keys(username)
        
                pwdElement.click()
                pwdElement.clear()
                pwdElement.send_keys(password)

                pwdElement2.click()
                pwdElement2.clear()
                pwdElement2.send_keys(password)

                pinElement.click()
                pinElement.clear()
                pinElement.send_keys(pin)

                captcha_value = input("Please enter the captcha.")    
                captchaElement.click()
                captchaElement.clear()
                captchaElement.send_keys(captcha_value)
        
                submitElement.click()
        
                time.sleep(0.8)

                if identifyPage("mnemonic") != "mnemonic":
                    logger.error('Not on the mnemonic page.')
                    # it might just be a captcha error
                    return False
                else:
                    # should we save the username?

                    # let's pick the mnemonic
                    mnemonicElement = alphaspider.find_element_by_xpath('//div[@class="infoboxbody"]/p[@class="std"][2]')
                    mnemonic_text = mnemonicElement.get_attribute("innerText")  
                    mnemonicElement2 = alphaspider.find_element_by_xpath('//form[@name="formMnemonic"]//input[@class="std"]')

                    mnemonicElement2.click()
                    mnemonicElement2.clear()
                    mnemonicElement2.send_keys(mnemonic_text)

                    submitElement2 = alphaspider.find_element_by_xpath('//input[@class="bstd" and @value="Continue"]')

                    # final step in user creation
                    submitElement2.click()
        
                    time.sleep(0.8)

                    if identifyPage("home") != "home":
                        return False
                    else:
                        return True
                  # <input class="bstd" value="Login" type="submit">
                
                
        except BaseException as e:
                # logger.error('Could not fill the log-in form. Please do it manually.: ' + str(e))
                logger.error('Could not fill the log-in form.')
                return False
    else:
        logger.critical("Cannot download the captcha. Stopping now.")
        return False

def totalProducts():
    # returns the total n of products in the db
    
    sql = 'select count(id) as count from alphaspider'
    db_cursor.execute(sql)
    if db_total_products == db_cursor.fetchall():
        return db_total_products['count']
    else:
        return False

def printLog():
    # will print how long the spider has been running
    # and how many products are in the db
    logger.info("Test")


def identifyPage(page):
    # check if the current page is any of the significant pages. 
    # return True
    
    identified_page = False
    try:        
        if page == "login" and alphaspider.find_element_by_id('captcha'):
            identified_page = "login"
            logger.debug("This is the login page.")
        elif page == "product" and alphaspider.find_element_by_xpath("//span[@class='std']/b[contains(text(),'Purchase price')]"):
            identified_page = "product"
            logger.debug("This is a product page.")
        elif page == "home" and alphaspider.find_element_by_xpath("//h1[@class='std' and contains(text(),'Welcome, ')]"):
            identified_page = "home"
            logger.debug("This is the home page.")
        elif page == "mnemonic" and alphaspider.find_element_by_xpath("//h1[@class='infobox' and contains(text(),'Your Mnemonic')]"):
            identified_page = "mnemonic"
            logger.debug("This is the mnemonic page.")
            
    except NoSuchElementException as e:
        # print("identifyPage error: {0}".format(str(e)))
        # print(e)
        # 
        # do nothing, it's normal to have exceptions here
        # sys.exc_clear()
        logger.warning("Something went wrong when trying to check if this page: {} is a {} page".format(alphaspider.current_url, page))
        pass    
    
    return identified_page

def saveCaptcha():
    # Saves the captcha

    # now that we have the preliminary stuff out of the way time to get that image :D
    captcha = alphaspider.find_element_by_id('captcha')  # find part of the page you want image of
    captcha_location = captcha.location
    captcha_size = captcha.size
    
    # let's try to have a unique temp file
    screenshot_folder = os.path.join(project_home, 'data', 'screenshots')
    # screenshot_file = tempfile.NamedTemporaryFile(suffix='_suffix', prefix='prefix_', dir=screenshot_folder)
    screenshot_file = tempfile.NamedTemporaryFile(suffix='.jpg', prefix='captcha_screenshot_', dir=screenshot_folder, delete=False)
    # screenshot_file = os.path.join(project_home, 'data', 'screenshots', 'captcha.png')
    # alphaspider.save_screenshot(screenshot_file.name)  # saves screenshot of entire page
    file_name = screenshot_file.name
    screenshot_file.close()  
    
    alphaspider.get_screenshot_as_file(file_name)    
    # base64_image_data = alphaspider.get_screenshot_as_base64()
    # print(base64_image_data)
    
    # input("Please wait.")
    
    im = Image.open(file_name)  # uses PIL library to open image in memory
    
    left = captcha.location['x']
    top = captcha.location['y']
    right = captcha.location['x'] + captcha.size['width']
    bottom = captcha.location['y'] + captcha.size['height']
    
    # defines crop points
    im = im.crop((left, top, right, bottom)) 
    
    # saves new cropped image
    # im.save(os.path.join(project_home, 'data', 'screenshots', 'captcha_cropped.png'))
    captcha_file = tempfile.NamedTemporaryFile(suffix='.jpg', prefix='captcha_', dir=screenshot_folder, delete=False)
    
    try:
        # im.save returns none - hence jsut catching the exception
        im.save(captcha_file.name)
        
        logger.info("Captcha saved: " + captcha_file.name)
        
        return captcha_file.name
            
    except IOError:
        logger.error('Could not save the captcha.')
        return False

def deleteOldCaptcha():
    # This function will delete, by id, and old captcha
    print("Nothing works here yet")

def solveCaptcha(captcha_file_name):
    # Captcha solved, using third party service
    api = TwoCaptchaApi(captcha_key)
    
    with open(captcha_file_name, 'rb') as captcha_file:
        captcha = api.solve(captcha_file)

    captcha_result = captcha.await_result()
    
    logger.info("Captcha solved: " + captcha_result)
    
    return captcha_result

def dbConnect():
    # connects to the DB 
    
    global connection, db_cursor
    connection = MySQLdb.connect(host=db_connection['host'], user=db_connection['user'], \
                                 passwd=db_connection['passwd'], db=db_connection['db'], charset='utf8', use_unicode=True)
    db_cursor = connection.cursor(MySQLdb.cursors.DictCursor)

    # uncommenting the next 2 lines (15/6 as problems still come up)
    db_cursor.execute("set names utf8mb4") 
    db_cursor.execute("set character set utf8mb4") 

    if db_cursor:
        return True
    else:
        return False

def dbGetProducts():
    # will get the list of products already saved    
       
    sql = "SELECT id FROM `alphaspider` order by id"
    
    db_cursor.execute(sql)
    db_products = db_cursor.fetchall()
    return db_products

def getUrl(url):
    # gets a URL, using a random timer
    
    time.sleep(random.uniform(0.5, 0.95))
    try:
        alphaspider.get(url)
        
        # do sanity checks on the page received.
        
        # e.g. check if we need to slow down
        
        
        
        
        return True
    except:
        logger.error("Cannot get " + url + " correctly. Currently at " + alphaspider.current_url + ".")
        # will now try to save a screenshot
        saveScreenShot()
        # are we logged out?
        if identifyPage("login") == "login":
            sys.exit("Something is broken.")        
        
        # alphaspider.send_keys(Keys.CONTROL + 'Escape')
        # alphaspider.get(site_home)
        return False
    # not sure if it would be appropriate to load the home.
    

def getVars():    
    # open the vars from the pickle  
      
    with open(picklefile, 'rb') as pickleFile:
        savedVars = pickle.load(pickleFile)
        
    return savedVars
        
def saveVars():
    # saves the vars in a pickle file
    
    # let's save categories, cookies etc
    savedVars['cookies'] = alphaspider.get_cookies() 
        
    with open(picklefile, 'wb') as pickleFile:
    # dump your data into the file
        pickle.dump(savedVars, pickleFile)
        return True
    

def dbSaveProduct(product):    
    # saves a product in the database
    
    sql = """INSERT IGNORE INTO `alphaspider` (`id`, `title`, `brief`, `ad`, `price`, `url`, `seller`, `origin`, `destination`, `payment`, `sold_since`, `products_sold`, `category`, `image`) 
    VALUES (%(id)s, %(title)s, %(brief)s, %(ad)s, %(price)s, %(url)s, %(seller)s, %(origin)s, %(destination)s, %(payment)s, %(sold_since)s, %(products_sold)s, %(category)s, %(image)s);"""
    db_cursor.execute(sql, product)
    connection.commit()

def autoLogin():
    # logs in automatically in the web site, using one of the given users.
    
    # alphaspider.get(site_login)
    getUrl(site_login)
    # first of all, let's download the captcha
    
    captcha_file = saveCaptcha()
    
    if captcha_file:   
        # sys.exit("Just testing.") 
        # let's pass this value to the captcha solver 
        captcha_value = solveCaptcha(captcha_file)        
        
        if captcha_value:
    
            # get username and password fields
            try:
                # <input name="user" class="std" size="65" value="" type="text">
                nameElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="user"]')
                pwdElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="pass"]')
                captchaElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="captcha_code"]')
                submitElement = alphaspider.find_element_by_xpath('//input[@class="bstd" and @value="Login"]')
        
                nameElement.click()
                nameElement.clear()
                nameElement.send_keys(alphauser)
        
                pwdElement.click()
                pwdElement.clear()
                pwdElement.send_keys(alphapwd)
        
                # captcha_value = input("Please enter the captcha.")
        
                captchaElement.click()
                captchaElement.clear()
                captchaElement.send_keys(captcha_value)            
                
                # alphaspider.find_element_by_xpath("//h1[@class='std' and contains(text(),'Welcome, ')]")
        
                submitElement.click()
        
                time.sleep(0.8)
    
                if identifyPage("home") != "home":
                    return False
                else:
                    return True
                # <input class="bstd" value="Login" type="submit">
                
                
            except BaseException as e:
                # logger.error('Could not fill the log-in form. Please do it manually.: ' + str(e))
                logger.error('Could not fill the log-in form.')
                return False
        else:
            logger.critical("Cannot solve the captcha. Will retry.")
            return False
        

    else:
        logger.critical("Cannot download the captcha. Stopping now.")
        return False

def startSpider():
    # Starts the spider
    
    global alphaspider
        
    # set a logfile
    webdriver.firefox.logfile = logfile
        
    # now will set the profile settings, using a blank profile.
    # the Tor profile folder is too messy to be used.
    # profile = webdriver.FirefoxProfile(tor_profile_folder)

    profile = webdriver.FirefoxProfile()
    
    # set some privacy settings
    profile.set_preference("network.cookie.lifetimePolicy", 2)
    profile.set_preference("network.dns.disablePrefetch", True)
    profile.set_preference("network.http.sendRefererHeader", 0)
    profile.set_preference("javascript.enabled", False)

    # set socks proxy
    profile.set_preference("network.proxy.type", 1)
    profile.set_preference("network.proxy.socks_version", 5)
    profile.set_preference("network.proxy.socks", '127.0.0.1')
    profile.set_preference("network.proxy.socks_port", tor["socks_port"])
    profile.set_preference("network.proxy.socks_remote_dns", True)
    
    # added on 15/06 - untested
    profile.set_preference("http.response.timeout", 10)
    profile.set_preference("dom.max_script_run_time", 10)
      
    # workaround for bug in current Selenium
    caps = webdriver.DesiredCapabilities().FIREFOX
    caps["marionette"] = False
    caps["javascriptEnabled"] = False
    
    # set the binary file

    alphaspider = webdriver.Firefox(capabilities=caps, firefox_binary=gecko_binary, firefox_profile=profile)
    # browser = webdriver.Firefox(capabilities=caps,firefox_binary=gecko_binary)   
    alphaspider.maximize_window()
    # starting the tor browser may take some time
    
    # get the login URL
#    autologin_successful = autoLogin()
#    while autologin_successful == False:
#        logger.info("Let's try again.")
#        input("Press any key to start again.")
#        autologin_successful = autoLogin()

    # let's try the same but with new users
    new_user_successful = newUser()

#    if new_user_successful == False:
#        sys.exit("Something is broken.") 
    
    while  new_user_successful == False:
        logger.info("Let's try again.")
        new_user_successful = newUser()
        
    return True

def startLightWeightSpider():
    # starts the lightweight browser
    
    global alphaspider
    
    caps2 = dict(webdriver.DesiredCapabilities.PHANTOMJS)
    caps2["phantomjs.page.settings.userAgent"] = ("Mozilla/5.0 (Windows NT 6.1; rv:45.0) Gecko/20100101 Firefox/45.0")
    service_args = [
        '--proxy=127.0.0.1:9150',
        '--proxy-type=socks5',
        '--ignore-ssl-errors=true',
        '--ssl-protocol=any'
    ]
    alphaspider = webdriver.PhantomJS(desired_capabilities=caps2, service_args=service_args)
    
    alphaspider.maximize_window()
    
    # get the login URL
    autologin_successful = autoLogin()
    while autologin_successful == False:
        logger.info("Let's try again.")
        autologin_successful = autoLogin()
        
    return True

def getProduct(url):
    # fetches all product details from an URL
    
    global saved_products
    # accesses the global counter
    
    # <h1 class="std">
    id_regexp = re.compile('[0-9]+$')
    id = id_regexp.search(url).group(0)
    
    logger.info('Fetching product #' + str(id))    
    
    if getUrl(url):
  
        # if tmp_page_type == "product":
        if identifyPage("product") == "product":
        
            try:
                # category_tmp = alphaspider.find_element_by_xpath("//div[@class='content']/div[@class='navbar']//a[string-length(text()) > 0]/text()")
                # note "elements" instead of "element"
                category_tmp = alphaspider.find_elements_by_xpath("//div[@class='content']/div[@class='navbar']//a")
                category_tmp = category_tmp[1:-1]
                category = ""
                for i in category_tmp:
                    category = category + "/" + i.get_attribute("innerText")
                # print("category:" + category)        
            except:
                logger.warning("Cannot get category correctly:", sys.exc_info()[0])
            
            try:
                title = alphaspider.find_element_by_xpath('//h1[@class="std"]').get_attribute("innerHTML")
                brief = alphaspider.find_element_by_xpath('//h1[@class="std"]/following-sibling::p[@class="std"]').get_attribute("innerHTML")
                # <div id="div_content1"
                ad = alphaspider.find_element_by_xpath('//div[@id="div_content1"]').get_attribute("innerHTML")
                # <span class="std"><b>Purchase price:</b> USD 14.99</span>
                # "//*[text() = 'foobar']"
                
                price_tmp = alphaspider.find_element_by_xpath("//span[@class='std']/b[contains(text(),'Purchase price')]/..")
                price_regexp = re.compile('USD [0-9\.\,]+')
                price = price_regexp.search(price_tmp.get_attribute("innerHTML")).group(0)
                
                # <a class="std" href="user.php?id=GoodGuys00">GoodGuys00</a>
                seller = alphaspider.find_element_by_xpath("//a[contains(@href,'user.php?id=')]").get_attribute("innerText")  
                origin = alphaspider.find_element_by_xpath("//div/span/b[text()='Origin country']/../../following-sibling::div[1]/span").get_attribute("innerText") 
                destination = alphaspider.find_element_by_xpath("//div/span/b[text()='Ships to']/../../following-sibling::div[1]/span").get_attribute("innerText") 
                payment = alphaspider.find_element_by_xpath("//div/span/b[text()='Payment']/../../following-sibling::div[1]/span").get_attribute("innerText") 
                # this one is slightly different
                
                sold_since_tmp = alphaspider.find_element_by_xpath("//p[contains(text(),'Sold by')]/i[2]").get_attribute("innerText")                
                sold_since_tmp2 = datetime.strptime(sold_since_tmp, '%b %d, %Y')
                sold_since = sold_since_tmp2.strftime('%Y-%m-%d')  
                products_sold = alphaspider.find_element_by_xpath("//p[contains(text(),'Sold by')]/i[1]").get_attribute("innerText") 
                
                image = alphaspider.find_element_by_xpath("//img[@class='listing']/..").get_attribute("href") 
                
                # print("image url: " + str(image))
                
                product = {'id': id,
                    'title': title,
                    'brief': brief,
                    'ad': ad,
                    'price': price,
                    'url' : url,
                    'seller' : seller,
                    'origin' : origin,
                    'destination' : destination,
                    'payment' : payment,
                    'sold_since' : sold_since,
                    'products_sold' : products_sold,
                    'category': category,
                    'image': image
                    # timestamp, category path
                }
                dbSaveProduct(product)
                
                saved_products = saved_products + 1
                
                return product  
            except BaseException as e:
                # sys.exc_info()[0]
                logger.error("Cannot parse xpath correctly in product page:", url)
                return False
            # navbar_elements = alphaspider.find_element_by_xpath("//div[@class='content']/div[@class='navbar']//a[string-length(text()) > 0]/text()")
        else:
            logger.warning("Not a product page ({})".format(url))
            
            if(identifyPage("login") == "login"):
                # something is broken, must kill the script
                sys.exit("Something is broken.")
                
            # check if we are still logged in
            
            
            
            return False
    else:
        # no need for a message - already captured in getUrl
        # print("Cannot get url " + url)
        return False
    
def getImage(url):
    # this function will get the main image for a specific product
    # will save it locally, for now   
    print("This is just a placeholder for now") 

def uploadFile(file, path):
    # This is an helper function to upload files. It will have to be refined depending on the storage used.
    # paths: data/screenshots, data/products, data/captchas

    s3_client = boto3.client('s3', aws_access_key_id=boto3_settings['aws_access_key_id'], aws_secret_access_key=boto3_settings['aws_secret_access_key'], region_name=boto3_settings['region_name'])
    
    if s3_client.upload_file(file, aws_bucket, path):
        return True
    else:
        return False        


def printProducts(products, product_attr):
    # prints a specific attribute for all the products in a product list, in the terminal
    # e.g.: printProducts(products, "brief")
    
    for i in products:
        print(''.join(c for c in i[product_attr] if c <= '\uFFFF'))


def getCategoryProducts(category, limit):
    # get the products in a category; it's just a front-end for runQuery
    
    url = site_category + str(category)
    products = runQuery(url, limit)
    return products
    
def getQueryProducts(query, limit):
    # get all the products in a query; it's just a front-end for runQuery
    
    url = site_search + urllib.urlencode(query)
    products = runQuery(url, limit)
    return products

def runQuery(query, limit):
    # runs a specific query against the market and obtains a product listing
    # should do a check here...
    
    product_URLs = []
    products = []

    last_page = findNumberOfPages(query)
    
    # if I cannot find the last page, it's probably something that doesn't exist any more
    
    if limit and limit > 0 and limit < last_page:
        last_page = limit
    
    # there should be some check here

    for i in range(1, last_page + 1):
        next_URL = query + '&pg=' + str(i)
        logger.info("Looking for products: " + next_URL)
        getUrl(next_URL)
        # alphaspider.get(next_URL)

        # todo: check how many pages
        
        body = alphaspider.find_elements_by_xpath('//*[@class="listing"]//a[@class="bstd"]')
        for element in body:
            # print(element.get_attribute("href"))
            product_URLs.append(element.get_attribute("href"))

    # remove duplicates and sort
    product_URLs = sorted(set(product_URLs))

    # should check if the URL is already in a db
    for URL in product_URLs:
        # let's extract the id
        id_regexp = re.compile('[0-9]+$')
        id = id_regexp.search(URL).group(0)
        
        if not {'id': int(id)} in db_products:
            # print("Product #" + id + " has not been downloaded yet")
            product = getProduct(URL)
            if product:
                products.append(product)
        else:
            # printf("id {:s} already in the db".format(id))
            logger.info("id " + str(id) + " already in the db.")

    return products

def saveScreenShot():
    # savse a screenshot
    # now = str(datetime.datetime.now())
    # screenshot_file = os.path.join(project_home, 'data', 'screenshots',  now  + 'screnshot.png')

    trailer_string = hashlib.md5()
    trailer_string.update(alphaspider.current_url.encode())
    trailer_string2 = trailer_string.hexdigest()[-8:]
    
    screenshot_file = os.path.join(project_home, 'data', 'screenshots', trailer_string2 + '_screnshot.png')
    alphaspider.get_screenshot_as_file(screenshot_file)


def getCategories(url):
    # get all the categories and subcategories from the website
    
    global categories
    # short sleep
    # class="content1"
    logger.info("Searching for categories in " + url)
    
    # this function is changing a global variable
    # if you cannot open the url, just don't do anything 
    if getUrl(url):
        links = alphaspider.find_elements_by_xpath('//div[@class="content1"]//a[@class="category"]')
        
        if links:
            for element in links:
                href = element.get_attribute("href")
                regexp = re.compile('frc=([0-9]+)')
                cat = regexp.search(href).group(1)
                if cat and cat not in categories:
                    logger.info("Adding category: #" + cat)
                    categories.add(cat)
                    getCategories(site_category + str(cat))

def findNumberOfPages(url):
    # get the number of pages for a specific product search and/or category
    
    # get the item before this:
    # <img src="images/last.png" alt="" class="std" height="16" width="16">
    # <img src="images/nolast.png" alt="" class="std" height="16" width="16">
    # <a class="page" href="search.php?[...]&amp;pg=50"><img src="images/last.png" alt="" class="std" height="16" width="16"></a>
    # e = alphaspider.find_elements_by_xpath('//img[@src="images/last.png"]')
    last_page = 1 
    
    # if you cannot open the URL to find the number of pages
    # just return 1
    if getUrl(url):
        try:
            e = alphaspider.find_element_by_xpath('//img[@src="images/last.png"]/..')
        except NoSuchElementException:    
            try:
                e = alphaspider.find_element_by_xpath('//img[@src="images/nolast.png"]/..')
            except NoSuchElementException:
                logger.error("Cannot find the # of pages for the query " + url)
        
        # default value
           
        if 'e' in locals():
            # print(str(e))
            try:
                href = e.get_attribute("href")
                last_page = int(re.compile('pg=([0-9]+)').search(href).group(1))
            except:
                logger.error("Cannot find the last page for query " + url)
        
        # there should be a case for wrong queries
        
    return last_page

os.chdir(project_home)
if not 'alphaspider' in locals():
    
    start_time = time.monotonic()
    saved_products = 0
    
    # let's see if there are any command line options
    setOptions()
    
    # set up db; will connect to db, load db_products
    if checkSettings():
        
        startSpider()
        # startLightWeightSpider()
        alphaspider.set_script_timeout(30)
        alphaspider.set_page_load_timeout(30)
    
        # check if we are not logged in
        # this will not work with a headless browser - may need to rewrite this part
        # the next 2 lines should be out of date
        # while identifyPage("home") != "home":
        #    input("Press recheck your login details, and Enter to continue.")
    
        # categories = set([])
        # categories = getCategories(site_home)
        # saveVars()
        saveScreenShot()
        max_pages = 25
        # tmp_categories = set(categories)
        tmp_categories = random.sample(categories, 30)
    
        for category in tmp_categories:
            logger.info("Getting category: " + str(category))
            products = getCategoryProducts(category, max_pages)
           
            # this doesn't work
            # refresh the db of products after each category
            db_products = dbGetProducts()
            products_per_hour = saved_products / ((time.monotonic() - start_time) / 60 / 60)
            logger.info("{0} products in db. Downloading {1:.2f} items/hour".format(len(db_products), products_per_hour))
            # test: how long has this been running? If over an hour, let's just stop now and restart
            if time.monotonic() - start_time > 3600:
                logger.info("Time to stop. No point in raising suspicions.")
                break