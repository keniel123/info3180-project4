from datetime import datetime, timedelta
import os
from random import randint
import jwt
import json
import requests
import base64
import time
from project import thumbnail,sendmail
from functools import wraps
from urlparse import parse_qs, parse_qsl
from urllib import urlencode
from flask import Flask, g, send_file, request, redirect, url_for, jsonify,session
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from requests_oauthlib import OAuth1
from project.models import User ,Wish
from project import app,db,bcrypt
from jwt import DecodeError, ExpiredSignature



def create_token(user):
    payload = {
        'sub': user.userid,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=14)
    }
    token = jwt.encode(payload, app.config['TOKEN_SECRET'])
    return token.decode('unicode_escape')


def parse_token(req):
    token = req.headers.get('Authorization').split()[1]
    return jwt.decode(token, app.config['TOKEN_SECRET'])


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.headers.get('Authorization'):
            response = jsonify(message='Missing authorization header')
            response.status_code = 401
            return response

        try:
            payload = parse_token(request)
        except DecodeError:
            response = jsonify(message='Token is invalid')
            response.status_code = 401
            return response
        except ExpiredSignature:
            response = jsonify(message='Token has expired')
            response.status_code = 401
            return response

        g.user_id = payload['sub']

        return f(*args, **kwargs)

    return decorated_function



@app.route('/')
def index():
    return app.send_static_file('index.html')







@app.route('/api/user/login', methods=['POST'])
def login():
    user = User.query.filter_by(email=request.json['email']).first()
    if not user or not bcrypt.check_password_hash(user.password,request.json['password']):
        response = jsonify({"error":"1","data":{},"message":'failed'})
        response.status_code = 401
    else:
        token = create_token(user)
        payload = jwt.decode(token,app.config['TOKEN_SECRET'], algorithm=['HS256']) 
        response = jsonify(token=token,information={"error":"null","data":{'token':token,'expires': timeinfo(payload['exp']),'user':{'id':user.userid,'email': user.email,'name':user.display_name},"message":"Success"}})
    return response



@app.route('/api/user/register', methods=['POST'])
def signup():
    json_data = request.json
    user = User(
         userid = randint(620000000,620099999),
         display_name=json_data['displayName'],
         email=json_data['email'],
         password=json_data['password'],
         profile_added_on=datetime.now())
    if user:
        db.session.add(user)
        db.session.commit()
        token = create_token(user)
        payload = jwt.decode(token,app.config['TOKEN_SECRET'], algorithm=['HS256']) 
        response = jsonify(token=token,information={"error":"null","data":{'token':token,'expires': timeinfo(payload['exp']),'user':{'id':user.userid,'email': user.email,'name':user.display_name},"message":"Success"}})
    else:
        response = jsonify({"error":"1","data":{},"message":'failed'})
    return response
        #token = AuthToken()
        #response = token.__repr__()
        #return jsonify(response)


@app.route('/api/user/<userid>/wishlist',methods=["GET","POST"])
@login_required
def wishes(userid):
    json_data = request.json
    if request.method=="GET":
        user = db.session.query(User).filter_by(userid=userid).first()
        wishes = db.session.query(Wish).filter_by(user_id=user.userid).all()
        wishlist = []
        for wish in wishes:
            wishlist.append({'id':wish.Id,'title': wish.title,'description':wish.description,'url':wish.url,'priority':wish.priority,'thumbnail':wish.imageUrl,'added_on':wish.added_on})
        if(len(wishlist)>0):
            response = jsonify({"error":"null","data":{"wishes":wishlist},"message":"Success"})
        else:
            response = jsonify({"error":"1","data":{},"message":"No such wishlist exists"})
        return response
    elif request.method == "POST":
        user = db.session.query(User).filter_by(userid=userid).first()
        wish = Wish(Id = randint(000000000,999999999),priority= json_data['priority'],user_id = user.userid,title = json_data['title'],url = json_data['url'],description = json_data['description'],imageUrl = json_data['thumbnail'],added_on= datetime.now())
        if wish:
            db.session.add(wish)
            db.session.commit()
            response = jsonify({"error":"null","data":{'title': wish.title,'description':wish.description,'url':wish.url,'thumbnail':wish.imageUrl},"message":"Success"})
        else:
            response = jsonify({"error":"1", "data":{},"message":"No such wishlist exists"})
        return response


@app.route('/api/user/<userid>/wishlist/delete/<wishid>', methods=["POST"])
@login_required
def deletewish(userid,wishid):
    if request.method =="POST":
        user = db.session.query(User).filter_by(userid=userid).first()
        wish = db.session.query(Wish).filter_by(Id=wishid).first()
        db.session.delete(wish)
        db.session.commit()
        response = jsonify({'error':'null','message':"Success"})
        return response
    else:
        response = jsonify({'error':'1','message':"Failed"})
        return response



@app.route('/api/thumbnail/process', methods=['GET','POST'])
def get_images():
    url = request.json['url']
    urlReal = url['url']
    urlReal.encode("ISO-8859-1")
    data = thumbnail.get_data(urlReal)
    if data:
        response = jsonify({'error':'null', "data":{"thumbnails":data},"message":"Success"})
    else:
        response = jsonify({'error':'1','data':{},'message':'Unable to extract thumbnails'})
    return response
    

@app.route('/api/getUser',methods=['GET','POST'])
@login_required
def getId():
   json_data= request.json
   user = User.query.filter_by(email=json_data['email']).first()
   return jsonify({"userid":user.userid})


@app.route('/api/user/<userid>/wishlistshare', methods=['POST'])
@login_required
def sharewishlist(userid):
    if request.method == 'POST':
        emails= []
        json_data = request.json
        user = db.session.query(User).filter_by(userid=userid).first()
        emails.append(json_data['email1'])
        emails.append(json_data['email2'])
        emails.append(json_data['email3'])
        emails.append(json_data['email4'])
        fromname = user.display_name
        fromaddr = user.email
        subject = "Hey Check out My WishList"
        link = "http://"+ app.config['host'] + "/" + str(app.config['port']) + "/api/user/" + userid + "/wishlist"
        msg = "Hey friend please check out this link to my wishlist :) " + "" + link
        for email in emails:
            if email:
                sendmail.sendemail(email,fromaddr,fromname,subject,msg)
        response = jsonify({"error":"null", "message":"Success"})
        return response
    else: 
        response = jsonify({"error":"Form Error","message":"Failed"})
        return response

@app.route('/api/user/getUrl', methods=['GET'])
def url():
    if request.method == 'GET':
        return str(app.config['port'])


def timeinfo(entry):
    day = time.strftime("%a")
    date = time.strftime("%d")
    if (date <10):
        date = date.lstrip('0')
    month = time.strftime("%b")
    year = time.strftime("%Y")
    return day + ", " + date + " " + month + " " + year

