#!/usr/bin/env python
"""
ab spider, proof-of-concept. If you are interested in the software, get in touch.

@author: Andres Baravalle
"""

# Notes: should we connect to MySQL via SSH? 
# e.g. plink.exe baravalle.com -P 22 -l andres -i C:\Users\andres2\Dropbox\Andres\ssh\mildred.ppk -L 127.0.0.1:3307:127.0.0.1:3306

# Pick seller, origin, destination, timestamp
# Freshen links after some days?
# move from Firefox to phantom.js after login?

import os
import datetime
#import pandas as pd
import re
import sys
import sqlalchemy
import subprocess
import shlex
import urllib
from selenium import webdriver
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from pprint import pprint
from settings import *

__version__ = '0.0.1'


# will include the categories with products
categories = set([])

def dbConnect():
    engine = sqlalchemy.create_engine(db_connection, echo=True)
    connection = engine.connect()
    # result = connection.execute(alphaspider.select())


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

def getProduct(url):
    # fetches all product details from an URL
    # <h1 class="std">
    alphaspider.get(url)
    title = alphaspider.find_element_by_xpath('//h1[@class="std"]')
    brief = alphaspider.find_element_by_xpath('//h1[@class="std"]/following-sibling::p[@class="std"]')
    # <div id="div_content1"
    ad = alphaspider.find_element_by_xpath('//div[@id="div_content1"]')
    # <span class="std"><b>Purchase price:</b> USD 14.99</span>
    # "//*[text() = 'foobar']"
    price_tmp = alphaspider.find_element_by_xpath("//span[@class='std']/b[contains(text(),'Purchase price')]/..")
    price_regexp = re.compile('USD [0-9\.\,]+')
    price = price_regexp.search(price_tmp.get_attribute("innerHTML")).group(0)

    return {'title': title.get_attribute("innerHTML"),
            'brief': brief.get_attribute("innerHTML"),
            'ad': ad.get_attribute("innerHTML"),
            'price': price,
            'url' : url
            # seller, origin, destination, timestamp, category path
            }

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

    # ideally should look for a marker instead than loading 8 pages only
    for i in range (1,last_page):
        next_URL = query +'&pg='+str(i)
        alphaspider.get(next_URL)

        # todo: check how many pages
        
        body = alphaspider.find_elements_by_xpath('//*[@class="listing"]//a[@class="bstd"]')
        for element in body:
            print(element.get_attribute("href"))
            product_URLs.append(element.get_attribute("href"))

    # remove duplicates and sort
    product_URLs = sorted(set(product_URLs))

    # should check if the URL is already in a db
    for i in product_URLs:
        product = getProduct(i)
        if product:
            products.append(product)

    return products

def saveScreenShot():
    # get a screenshot
    now = str(datetime.datetime.now())
    screenshot_file = 'screenshots/' + now  + 'screnshot.png'
    alphaspider.get_screenshot_as_file(screenshot_file)


def dbConnect():
    


def getCategories(url):
    # get all the categories and subcategories from the website
    
    # class="content1"
    alphaspider.get(url)
    links = alphaspider.find_elements_by_xpath('//div[@class="content1"]//a[@class="category"]')
    
    for element in links:
        href = element.get_attribute("href")
        regexp = re.compile('frc=([0-9]+)')
        cat = regexp.search(href).group(1)
        
        categories.add(cat)
    
    categories = sorted(categories)

def findNumberOfPages(url):
    # get the item before this:
    # <img src="images/last.png" alt="" class="std" height="16" width="16">
    # <a class="page" href="search.php?[...]&amp;pg=50"><img src="images/last.png" alt="" class="std" height="16" width="16"></a>
    # e = alphaspider.find_elements_by_xpath('//img[@src="images/last.png"]')
    print("Test")
    alphaspider.get(url)
    e = alphaspider.find_element_by_xpath('//img[@src="images/last.png"]/..')
    href = e.get_attribute("href")
    last_page = int(re.compile('pg=([0-9]+)').search(href).group(1))
    return(last_page)

os.chdir(project_home)
if not 'alphaspider' in locals():
    alphaspider = startSpider()

input("Press Enter to continue ('now$vl')...")
# products = getCategoryProducts('72')



