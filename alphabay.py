#!/usr/bin/env python
"""
ab spider, proof-of-concept. If you are interested in the software, get in touch.

@author: Andres Baravalle
"""

# Pick escrow
# user alphaspider.set_page_load_timeout(30) and catch exceptions
# check if a proxy is already running in the port
# set command line options
# check if the same page is downloaded over and over 
# Freshen links after some days?
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
# check if the combination of product and category has been saved; if the product is in the db, check against the current category
# identify features? e.g. if 75% of the images are identical, it's the same page
# it the proxy (tor) is refusing a connection
# check if logged in!
# check if in a product page!
# check if in a category page!
# check if in the login screen
# check if logged in (string Welcome, AntoinFlags)

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
from pprint import pprint
#from settings import *
from settings_laptop import *
import time

__version__ = '0.0.1'


# will include the categories with products

def checkSettings():
    # This function will check all the settings
    if os.path.isdir(project_home):
            print("Test passed: project home.")
    if os.path.isdir(tor_profile_folder):
            print("Test passed: Tor profile home.")
    
#tor_profile_folder

def setOptions():
    # setting global variables
    global project_home, tor_profile_folder, gecko_binary, alphauser, alphapsw, db, tor_cmd, tor_args
    
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
        tor_cmd = args.tor_cmd
    if args.tor_args:
        tor_args = args.tor_args
    

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
        elif page == "home" and alphaspider.find_element_by_xpath("//h1[@class='std' and contains(text(),'Welcome, {}')]".format(alphauser)):
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

def saveCaptcha():
    #fox = webdriver.Firefox()
    #fox.get('https://stackoverflow.com/')
    # '//img[@id="captcha"]'
    # now that we have the preliminary stuff out of the way time to get that image :D
    captcha = alphaspider.find_element_by_id('captcha') # find part of the page you want image of
    captcha_location = captcha.location
    captcha_size = captcha.size
    screenshot_file = 'data/screenshots/screnshot.png'
    alphaspider.save_screenshot(screenshot_file) # saves screenshot of entire page
    
    im = Image.open(screenshot_file) # uses PIL library to open image in memory
    
    left = captcha.location['x']
    top = captcha.location['y']
    right = captcha.location['x'] + captcha.size['width']
    bottom = captcha.location['y'] + captcha.size['height']
    
    
    im = im.crop((left, top, right, bottom)) # defines crop points
    im.save('data/screenshots/screnshot_cropped.png') # saves new cropped image


def dbGetProducts():
    # will get the list of products already saved    
    sql = "SELECT id FROM `alphaspider` order by id"
    
    db_cursor.execute(sql)
    db_products = db_cursor.fetchall()
    return db_products

def getUrl(url):
    alphaspider.set_script_timeout(25)
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
 
    sql = """INSERT IGNORE INTO `alphaspider` (`id`, `title`, `brief`, `ad`, `price`, `url`, `seller`, `origin`, `destination`, `payment`, `sold_since`, `category` ) 
    VALUES (%(id)s, %(title)s, %(brief)s, %(ad)s, %(price)s, %(url)s, %(seller)s, %(origin)s, %(destination)s, %(payment)s, %(sold_since)s, %(category)s);"""
    db_cursor.execute(sql, product)
    connection.commit()

def startSpider():
    ### Starts the spider ###
    # set a logfile
    webdriver.firefox.logfile = logfile

    # starts tor from the command line
    subprocess.Popen([tor_cmd] + shlex.split(tor_args))
    
    # set the profile
    # profile = webdriver.FirefoxProfile(tor_profile_folder)
    
    # workaround for bug in current Selenium
    caps = webdriver.DesiredCapabilities().FIREFOX
    caps["marionette"] = False
    
    # set the binary file
    browser = webdriver.Firefox(capabilities=caps,firefox_binary=gecko_binary)   
    browser.maximize_window()
    # starting the tor browser may take some time
    
    # get the login URL
    browser.get(site_login)
    
    # get username and password fields
    try:
        # <input name="user" class="std" size="65" value="" type="text">
        nameElement = browser.find_element_by_xpath('//input[@class="std" and @name="user"]')
        pwdElement = browser.find_element_by_xpath('//input[@class="std" and @name="pass"]')
        captchaElement = browser.find_element_by_xpath('//input[@class="std" and @name="captcha_code"]')
        submitElement = browser.find_element_by_xpath('//input[@class="bstd" and @value="Login"]')

        nameElement.click()
        nameElement.clear()
        nameElement.send_keys(alphauser)

        pwdElement.click()
        pwdElement.clear()
        pwdElement.send_keys(alphapwd)

        captchaElement.click()

        input("Press Enter to continue.")

        submitElement.click()

        
        # <input class="bstd" value="Login" type="submit">
        
        
    except BaseException as e:
       # logger.error('Could not fill the log-in form. Please do it manually.: ' + str(e))
       print('Could not fill the log-in form. Please do it manually.: ' + str(e))
    
    time.sleep(0.8)
    return browser

def startLightWeightSpider():
    caps = dict(webdriver.DesiredCapabilities.PHANTOMJS)
    caps["phantomjs.page.settings.userAgent"] = ("Mozilla/5.0 (Windows NT 6.1; rv:45.0) Gecko/20100101 Firefox/45.0")
    service_args = [
    '--proxy=127.0.0.1:9150',
    '--proxy-type=socks5',
    ]
    browser = webdriver.PhantomJS(desired_capabilities=caps, service_args=service_args)
    
    return browser

def getProduct(url):
    # fetches all product details from an URL
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
                    category = category + "/" +  i.get_attribute("innerText")
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
                    'category': category
                    # timestamp, category path
                    }
                dbSaveProduct(product)
                
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
    url = site_search+urllib.urlencode(query)
    products = runQuery(url, limit)
    return products

def runQuery(query, limit):
    # runs a specific query against the market and obtains a product listing
    # should do a check here...
    
    product_URLs = []
    products = []

    last_page = findNumberOfPages(query)
    
    if limit and limit > 0 and limit < last_page:
        last_page = limit
    
    # there should be some check here

    for i in range (1,last_page+1):
        next_URL = query +'&pg='+str(i)
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
    now = str(datetime.datetime.now())
    screenshot_file = 'data/screenshots/' + now  + 'screnshot.png'
    alphaspider.get_screenshot_as_file(screenshot_file)


def getCategories(url):
    # get all the categories and subcategories from the website
    global categories
    # short sleep
    time.sleep(random.uniform(0.1, 0.9))
    # class="content1"
    print ("Searching for categories in " + url)
    
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
        except (NoSuchElementException):    
            try:
                e = alphaspider.find_element_by_xpath('//img[@src="images/nolast.png"]/..')
            except (NoSuchElementException):
                print("Cannot find the # of pages for the query " + url)
        
        # default value
           
        if e:
            href = e.get_attribute("href")
            last_page = int(re.compile('pg=([0-9]+)').search(href).group(1))
        
    return(last_page)

os.chdir(project_home)
if not 'alphaspider' in locals():
    start_time = time.monotonic()
    connection = MySQLdb.connect(host=db_connection['host'], user=db_connection['user'], \
                                 passwd=db_connection['passwd'], db=db_connection['db'], charset='utf8', use_unicode=True)
    db_cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    #db_cursor.execute("set names utf8mb4") 
    #db_cursor.execute("set character set utf8mb4") 
    alphaspider = startSpider()
    # saveCaptcha()

    # check if we are not logged in
    while identifyPage("home") != "home":
        input("Press recheck your login details, and Enter to continue.")

# should check if logged in   
# let's find the list of all products, ids only
db_products = dbGetProducts()

# if there are no products in a while we should kill the script
print("{0} products in db".format(len(db_products)))

#categories = set([])
savedVars = getVars()
categories = savedVars['categories']
print("Total n of categories: " + str(len(categories)))

# categories = getCategories(site_home)
# saveVars()

max_pages = 50
# tmp_categories = random.sample(categories, 30)
# tmp_categories = {2, 16, 17, 63}
#tmp_categories = {22, 23, 24, 25, 26, 27}
#tmp_categories.add(range(20, 27))
# tmp_categories = {140, 141, 142, 143, 144, 145, 146}
# tmp_categories = {67, 164, 165}
# tmp_categories = {23, 25, 27, 63}
tmp_categories = {7, 47, 48, 49, 50, 51, 52}
# tmp_categories = categories
for category in tmp_categories:
    products = getCategoryProducts(category,max_pages)
    now = time.monotonic()
    if (start_time - now) > 300:
        db_products = dbGetProducts()
        print("{0} products in db".format(len(db_products)))
        start_time = now



