#!/usr/bin/env python
"""
ab spider, proof-of-concept. If you are interested in the software, get in touch.

@author: Andres Baravalle
"""

# Pick escrow
# Rewrite all paths as os generic
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
# add random sleep
# user alphaspider.set_page_load_timeout(30) and catch exceptions
# report total number of products on start and on end
# helper function to check setup
# helper function to go around timeouts
# report products in db every so many fetches

import os
import datetime
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
from Pillow import Image
from random import shuffle
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from selenium.common.exceptions import NoSuchElementException
from pprint import pprint
from settings import *
import time

__version__ = '0.0.1'


# will include the categories with products


def logIn():
    # get username and password fields
    try:
        # <input name="user" class="std" size="65" value="" type="text">
        nameElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="user"]')
        pwdElement = alphaspider.find_element_by_xpath('//input[@class="std" and @name="password"]')

        nameElement.send_keys(alphauser)
        pwdElement.send_keys(alphapwd)
        
        saveCaptcha()
    except:
        print("Could not fill the log-in form. Please do it manually.")

def saveCaptcha():
    fox = webdriver.Firefox()
    fox.get('https://stackoverflow.com/')
    
    # now that we have the preliminary stuff out of the way time to get that image :D
    captcha = alphaspider.find_element_by_id('hlogo') # find part of the page you want image of
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
 
    # sql = """INSERT INTO `alphaspider` (`id`, `title`, `brief`, `ad`, `price`, `url`, `seller`, `origin`, `destination`) 
    # VALUES (%(id)s, %(title)s, %(brief)s, %(ad)s, %(price)s, %(url)s, '%(seller)s', '%(origin)s', '%(destination)s'));"""
    
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
    
    # starting the tor browser may take some time
    
    # get the login URL
    browser.get(site_login)
    
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
    
    alphaspider.get(url)
    
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
    except:
        print("Cannot parse xpath correctly:", sys.exc_info()[0])
        return False
    # navbar_elements = alphaspider.find_element_by_xpath("//div[@class='content']/div[@class='navbar']//a[string-length(text()) > 0]/text()")

    

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
    # runs a specific query against the market
    
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
    
    time.sleep(1)
    # class="content1"
    print ("Searching for categories in " + url)
    alphaspider.get(url)
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
    alphaspider.get(url)
    try:
        e = alphaspider.find_element_by_xpath('//img[@src="images/last.png"]/..')
    except (NoSuchElementException):    
        try:
            e = alphaspider.find_element_by_xpath('//img[@src="images/nolast.png"]/..')
        except (NoSuchElementException):
            print("Cannot find the # of pages for the query " + url)
    
    # default value
    last_page = 1    
    if e:
        href = e.get_attribute("href")
        last_page = int(re.compile('pg=([0-9]+)').search(href).group(1))
        
    return(last_page)

os.chdir(project_home)
if not 'alphaspider' in locals():
    connection = MySQLdb.connect(host=db_connection['host'], user=db_connection['user'], \
                                 passwd=db_connection['passwd'], db=db_connection['db'], charset='utf8', use_unicode=True)
    db_cursor = connection.cursor(MySQLdb.cursors.DictCursor)
    #db_cursor.execute("set names utf8mb4") 
    #db_cursor.execute("set character set utf8mb4") 
    alphaspider = startSpider()
    logIn()

input("Press Enter to continue.")
    
# let's find the list of all products, ids only
db_products = dbGetProducts()

#categories = set([])
savedVars = getVars()
categories = savedVars['categories']
print("Total n of categories: " + str(len(categories)))

# categories = getCategories(site_home)
# saveVars()

# alphaspider2 = startLightWeightSpider()


max_pages = 50
# tmp_categories = random.sample(categories, 1)
# tmp_categories = {5}
tmp_categories = categories
for category in tmp_categories:
     products = getCategoryProducts(category,max_pages)
#     for product in products:
#         dbSaveProduct(product)
#         # print "Saved "
#         connection.commit()

