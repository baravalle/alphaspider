#!/usr/bin/env python
"""
ab spider, proof-of-concept. If you are interested in the software, get in touch.

@author: Andres Baravalle
"""

# rewrite the category part of the scripts, to link a name to a cactegory id
# create kickstart function that will get parameters from anywhere
# timer that prints products doesn't work
# user alphaspider.set_page_load_timeout(30) and catch exceptions
# check if a proxy is already running in the port
# set command line options

# download image and upload on s3 or similar
# refactor to make object oriented
# move from Firefox to phantom.js after login?
# should pick also the number of sold items, and save in a different table with progression
# use log commands rather than print commands?
# create log file?
# add username and password to screen
# support multiple configuration files
# check price
# helper function to check setup
# helper function to go around timeouts
# write start time, and keep track of save items/hour
# check if the combination of product and category has been saved; 
#   if the product is in the db, check against the current category
# identify features? e.g. if 75% of the images are identical, it's the same page
# it the proxy (tor) is refusing a connection
# check if the same page is downloaded over and over (should be solved)
# Freshen links after some days?


# os should be first
import os
import argparse
import datetime
import logger
# using mysqlclient 
import MySQLdb
import pickle
import random
import re
import socket
import sys
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
# from settings import *
from settings_laptop import *
import time

__version__ = '0.0.1'


# will include the categories with products

def checkSettings():
    global categories, db_products, savedVars
    # This function will check all the settings
    tmp_return = True
    
    if os.path.isdir(project_home):
        print("Test passed: project home.")
        os.chdir(project_home)
    else:
        tmp_return = False
    if os.path.isdir(tor["profile_folder"]):
        print("Test passed: Tor profile home.")
    else:
        tmp_return = False
         
    # let's check if tor is already running in the target port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.bind(("127.0.0.1", tor["socks_port"]))
    except socket.error as e:
        print("Something is already running in the port. I'll assume it's tor.")
    else:
        # starts tor from the command line
        tor_args = r' --SocksPort {} --ControlPort {}'.format(tor["socks_port"], tor["control_port"])
        torprocess = subprocess.Popen([tor["cmd"]] + shlex.split(tor_args))
        if torprocess:
            print("The pid for the current tor proxy is: " + str(torprocess.pid))
    
    s.close()     
    
    if not dbConnect(): 
        tmp_return = False
    else:
    # should check if logged in   
    # let's find the list of all products, ids only
        db_products = dbGetProducts()
        
        if db_products:
            # if there are no products in a while we should kill the script
            print("{0} products in db".format(len(db_products)))
            
            savedVars = getVars()
            categories = savedVars['categories']
            print("Total n of categories: " + str(len(categories)))
            
        else:
            tmp_return = False
    
    return tmp_return
# tor_profile_folder

def setOptions():
    # setting global variables
    global project_home, tor, gecko_binary, alphauser, alphapsw, db
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_home", help="Set the project home in the local filesystem.")
    parser.add_argument("--tor_profile_folder", help="Set the profile folder for Tor.")
    parser.add_argument("--gecko_binary", help="Set the location for the gecko binary.")
    parser.add_argument("--verbosity", help="Set the level of verbosity.")
    parser.add_argument("--alphauser", help="Set the site username")
    parser.add_argument("--alphapsw", help="Set the site password")
    parser.add_argument("--db", help="Set the connection string for the db")
    parser.add_argument("--tor_cmd", help="Set the location for the Tor binary")
    parser.add_argument("--tor_args", help="Set any args for calling Tor (typically ports)")
    args = parser.parse_args()
    if args.verbosity:
        print("Verbosity turned on")

    # let's check the folders
    if args.project_home:
        project_home = args.project_home
    if args.tor_profile_folder:
        tor_profile_folder = args.tor_profile_folder
    if args.gecko_binary:
        gecko_binary = args.gecko_binary
    if args.alphauser:
        alphauser = args.alphauser
    if args.alphapsw:
        alphapsw = args.alphapsw
    if args.db:
        db = args.db
    if args.tor_cmd:
        tor["cmd"] = args.tor_cmd
    if args.tor_args:
        tor["args"] = args.tor_args
    

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
    print("Test")

def identifyPage(page):
    # check if it's the login page
    # if there is a captcha, it's likely it's the login page
    # return True
    identified_page = False
    try:        
        if page == "login" and alphaspider.find_element_by_id('captcha'):
            identified_page = "login"
            # print("This is the login")
        elif page == "product" and alphaspider.find_element_by_xpath("//span[@class='std']/b[contains(text(),'Purchase price')]"):
            identified_page = "product"
            # print("This is a product")
        elif page == "home" and alphaspider.find_element_by_xpath("//h1[@class='std' and contains(text(),'Welcome, ')]"):
            identified_page = "home"   
            
    except NoSuchElementException as e:
        # print("identifyPage error: {0}".format(str(e)))
        # print(e)
        # 
        # do nothing, it's normal to have exceptions here
        # sys.exc_clear()
        print(str(e))
        pass    
    
    return identified_page

def saveCaptcha(local_spider):
    # fox = webdriver.Firefox()
    # fox.get('https://stackoverflow.com/')
    # '//img[@id="captcha"]'
    # now that we have the preliminary stuff out of the way time to get that image :D
    captcha = local_spider.find_element_by_id('captcha')  # find part of the page you want image of
    captcha_location = captcha.location
    captcha_size = captcha.size
    screenshot_file = os.path.join(project_home, 'data', 'screenshots', 'captcha.png')
    local_spider.save_screenshot(screenshot_file)  # saves screenshot of entire page
    
    im = Image.open(screenshot_file)  # uses PIL library to open image in memory
    
    left = captcha.location['x']
    top = captcha.location['y']
    right = captcha.location['x'] + captcha.size['width']
    bottom = captcha.location['y'] + captcha.size['height']
    
    # defines crop points
    im = im.crop((left, top, right, bottom)) 
    
    # saves new cropped image
    im.save(os.path.join(project_home, 'data', 'screenshots', 'captcha_cropped.png'))

    return True

def dbConnect():
    # connects to DB and sets global variables
    
    global connection, db_cursor
    connection = MySQLdb.connect(host=db_connection['host'], user=db_connection['user'], \
                                 passwd=db_connection['passwd'], db=db_connection['db'], charset='utf8', use_unicode=True)
    db_cursor = connection.cursor(MySQLdb.cursors.DictCursor)

    # db_cursor.execute("set names utf8mb4") 
    # db_cursor.execute("set character set utf8mb4") 

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
    alphaspider.set_script_timeout(25)
    time.sleep(random.uniform(0.3, 0.55))
    try:
        alphaspider.get(url)
        return True
    except:
        print("Cannot get " + url + " correctly.")
        return False
    # not sure if it would be appropriate to load the home.
    

def getVars():    
      
    with open(picklefile, 'rb') as pickleFile:
        savedVars = pickle.load(pickleFile)
        
    return savedVars
        
def saveVars():
    
    # let's save categories, cookies etc
    savedVars['cookies'] = alphaspider.get_cookies() 
        
    with open(picklefile, 'wb') as pickleFile:
    # dump your data into the file
        pickle.dump(savedVars, pickleFile)
        return True
    

def dbSaveProduct(product):    
 
    sql = """INSERT IGNORE INTO `alphaspider` (`id`, `title`, `brief`, `ad`, `price`, `url`, `seller`, `origin`, `destination`, `payment`, `sold_since`, `products_sold`, `category`) 
    VALUES (%(id)s, %(title)s, %(brief)s, %(ad)s, %(price)s, %(url)s, %(seller)s, %(origin)s, %(destination)s, %(payment)s, %(sold_since)s, %(products_sold)s, %(category)s);"""
    db_cursor.execute(sql, product)
    connection.commit()

def autoLogin(local_spider):
    local_spider.get(site_login)
    
    # first of all, let's download the captcha
    
    if saveCaptcha(local_spider):    
    
        # get username and password fields
        try:
            # <input name="user" class="std" size="65" value="" type="text">
            nameElement = local_spider.find_element_by_xpath('//input[@class="std" and @name="user"]')
            pwdElement = local_spider.find_element_by_xpath('//input[@class="std" and @name="pass"]')
            captchaElement = local_spider.find_element_by_xpath('//input[@class="std" and @name="captcha_code"]')
            submitElement = local_spider.find_element_by_xpath('//input[@class="bstd" and @value="Login"]')
    
            nameElement.click()
            nameElement.clear()
            nameElement.send_keys(alphauser)
    
            pwdElement.click()
            pwdElement.clear()
            pwdElement.send_keys(alphapwd)
    
            captcha_value = input("Please enter the captcha.")
    
            captchaElement.click()
            captchaElement.clear()
            captchaElement.send_keys(captcha_value)            
            
            # alphaspider.find_element_by_xpath("//h1[@class='std' and contains(text(),'Welcome, ')]")
    
            submitElement.click()
    
            time.sleep(0.8)            
            # <input class="bstd" value="Login" type="submit">
            
            
        except BaseException as e:
            # logger.error('Could not fill the log-in form. Please do it manually.: ' + str(e))
            print('Could not fill the log-in form. Please do it manually.: ' + str(e))
        
        return local_spider
    else:
        print("Cannot download the captcha. Stopping now.")
        return False

def startSpider():
    ### Starts the spider ###
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
      
    # workaround for bug in current Selenium
    caps = webdriver.DesiredCapabilities().FIREFOX
    caps["marionette"] = False
    caps["javascriptEnabled"] = False
    
    # set the binary file

    browser = webdriver.Firefox(capabilities=caps, firefox_binary=gecko_binary, firefox_profile=profile)
    # browser = webdriver.Firefox(capabilities=caps,firefox_binary=gecko_binary)   
    browser.maximize_window()
    # starting the tor browser may take some time
    
    # get the login URL
    browser = autoLogin(browser)
        
    return browser

def startLightWeightSpider():
    caps2 = dict(webdriver.DesiredCapabilities.PHANTOMJS)
    caps2["phantomjs.page.settings.userAgent"] = ("Mozilla/5.0 (Windows NT 6.1; rv:45.0) Gecko/20100101 Firefox/45.0")
    service_args = [
        '--proxy=127.0.0.1:9150',
        '--proxy-type=socks5',
        '--ignore-ssl-errors=true',
        '--ssl-protocol=any'
    ]
    browser = webdriver.PhantomJS(desired_capabilities=caps2, service_args=service_args)
    
    browser.maximize_window()
    
    # get the login URL
    browser = autoLogin(browser)
        
    return browser

def getProduct(url):
    # fetches all product details from an URL
    global saved_products
    # accesses the global counter
    
    # <h1 class="std">
    id_regexp = re.compile('[0-9]+$')
    id = id_regexp.search(url).group(0)
    
    print('Fetching product #' + str(id))    
    
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
                print("Cannot get category correctly:", sys.exc_info()[0])
            
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
                    'category': category
                    # timestamp, category path
                }
                dbSaveProduct(product)
                
                saved_products = saved_products + 1
                
                return product  
            except BaseException as e:
                # sys.exc_info()[0]
                print("Cannot parse xpath correctly in product page:", str(e))
                return False
            # navbar_elements = alphaspider.find_element_by_xpath("//div[@class='content']/div[@class='navbar']//a[string-length(text()) > 0]/text()")
        else:
            print("Not a product page ({})".format(url))
            
            if(identifyPage("login") == "login"):
                # something is broken, must kill the script
                sys.exit("Something is broken.")
                
            # check if we are still logged in
            
            
            
            return False
    else:
        print("Cannot get url " + url)
        return False
    
def getImage(url):
    # this function will get the main image for a specific product
    # will save it locally, for now   
    print("This is just a placeholder for now") 

def printProducts(products, product_attr):
    # prints a specific attribute for all the products in a product list, in the terminal
    # e.g.: printProducts(products, "brief")
    for i in products:
        print(''.join(c for c in i[product_attr] if c <= '\uFFFF'))


def getCategoryProducts(category, limit):
    # get the products in a category
    # it's just a front-end for runQuery
    url = site_category + str(category)
    products = runQuery(url, limit)
    return products
    
def getQueryProducts(query, limit):
    # get all the products in a query
    # it's just a front-end for runQuery
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
        alphaspider.get(next_URL)

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
            print("id " + str(id) + " already in the db.")

    return products

def saveScreenShot():
    # get a screenshot
    # now = str(datetime.datetime.now())
    # screenshot_file = os.path.join(project_home, 'data', 'screenshots',  now  + 'screnshot.png')
    screenshot_file = os.path.join(project_home, 'data', 'screenshots', 'screnshot.png')
    alphaspider.get_screenshot_as_file(screenshot_file)


def getCategories(url):
    # get all the categories and subcategories from the website
    global categories
    # short sleep
    # class="content1"
    print("Searching for categories in " + url)
    
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
                    print("Adding category: #" + cat)
                    categories.add(cat)
                    getCategories(site_category + str(cat))

def findNumberOfPages(url):
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
                print("Cannot find the # of pages for the query " + url)
        
        # default value
           
        if 'e' in locals():
            print(str(e))
            try:
                href = e.get_attribute("href")
                last_page = int(re.compile('pg=([0-9]+)').search(href).group(1))
            except:
                print("Cannot find the last page for query " + url)
        
        # there should be a case for wrong queries
        
    return last_page

os.chdir(project_home)
if not 'alphaspider' in locals():
    
    start_time = time.monotonic()
    saved_products = 0
    
    # set up db; will connect to db, load db_products
    if checkSettings():
        
        # alphaspider = startSpider()
        alphaspider = startLightWeightSpider()
    
        # check if we are not logged in
        # this will not work with a headless browser - may need to rewrite this part
        while identifyPage("home") != "home":
            input("Press recheck your login details, and Enter to continue.")
    
        # categories = set([])
        # categories = getCategories(site_home)
        # saveVars()
        saveScreenShot()
        max_pages = 50
        tmp_categories = set(categories)
        # tmp_categories = random.sample(categories, 30)
    
        for category in tmp_categories:
            print("Getting category: " + str(category))
            products = getCategoryProducts(category, max_pages)
           
            # this doesn't work
            # refresh the db of products after each category
            db_products = dbGetProducts()
            products_per_hour = saved_products / ((time.monotonic() - start_time) / 60 / 60)
            print("{0} products in db. Downloading {1:.2f} items/hours".format(len(db_products), products_per_hour))



