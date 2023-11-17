from flask import Flask, render_template, redirect, url_for, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
#from .models import Users, Follows
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy.orm import relationship
import time
from flask_session import Session


app = Flask(__name__)


#making database schema
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.String, primary_key=True)
    top_track = db.Column(db.String)
    top_artists  = db.Column(db.String)
    profile_picture = db.Column(db.String)

class Follows(db.Model):
    follower_user_id = db.Column(db.String, ForeignKey('users.id'), nullable=False, primary_key=True)
    followed_user_id = db.Column(db.String, ForeignKey('users.id'), nullable=False, primary_key=True)
    follower_user = db.relationship("Users", foreign_keys=[follower_user_id])
    followed_user = db.relationship("Users", foreign_keys=[followed_user_id])

db.create_all()


#inclue secret key so we can later use "sessions" to store spotify data
#we store all token info in the session
#2 previous comments arent true now as the token info is stored in the cache_handler
#i changed this as the session was getting mixed up when multiple users tried to login
app.secret_key = "secretforsessions"
#the above line may no longer be necessary but it doesnt cause any issues, so why remove it?

#all the paramaters we pass to spotify to allow me to use API
#added cache handler should make work for multiple users
cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)


SpotifyOAuthData = SpotifyOAuth(
    client_id = "95cb7a03a44d445a9c83024b2cb2dab0",
    client_secret = "096f41ea16c545318fc53b15c50c90e4",
    #redirect_uri = "http://127.0.0.1:5000/callback",
    redirect_uri = "https://7d48-81-109-105-102.ngrok-free.app/callback",
    scope = "user-top-read user-read-private user-read-email",
    cache_handler=cache_handler
)
#the above code is the request we have to send to the spotify API to get info. 
#really shouldnt be storing the client id and client secret in github for security but oh well.

#to keep user logged in, the access token must be refreshed, this is done periodically and automatically
#every time this function is called, we check if the token is expired - if it is, then we refresh it
def refresh_token():
    #token_info = session.get("token_info", None)
    token_info = cache_handler.get_cached_token()
    if not session["token_info"]:
        redirect(url_for("login"))
    if token_info["expires_at"] < 60 + int(time.time()):
        token_info = SpotifyOAuthData.refresh_access_token(token_info["refresh_token"])
    return token_info

#if the user is not logged in, there will be no token in the cache_handler as only logged in users have this.
def check_login():
    #added this for new cache system
    #to fix problems with sessions
    token_info = cache_handler.get_cached_token()
    if token_info:
        try:
            token_info = refresh_token()
        except:
            return redirect(url_for("home"))
        sp = spotipy.Spotify(auth=token_info["access_token"])
        id = sp.current_user()["id"]
        return id
    else: return False

#redirects user to spotify login prompt, then spotify redirects to /callback
@app.route("/login")
def login():
    auth_url = SpotifyOAuthData.get_authorize_url()
    return redirect(auth_url)

#final of oath2 flow, allows us to save token info to session for later use
@app.route("/callback")
def callback():
    session.clear()
    token_info = SpotifyOAuthData.get_access_token(request.args.get("code"))

    #issue above. all token info is the same dispite different "code"
    #this issue is fixed, it was an issue with the session being shared between users when it shouldnt be. 
    #now used cache handling stuff to fix it

    #session["token_info"] = token_info
    #above is the only session code, this was replaced by cache handling stuff



    #if user hasnt logged in before, save them to our users table in database
    #this may randomly break no idea why
    #i No longer think this randomly breaks anymore
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))

    sp = spotipy.Spotify(auth=token_info["access_token"])
    id = sp.current_user()["id"]
    profile_picture = sp.current_user()["images"][0]["url"]

    top_artists = sp.current_user_top_artists(limit=5, time_range="medium_term")["items"]
    top_tracks = sp.current_user_top_tracks(limit=1, time_range="medium_term")["items"]
    #ids for artists
    #moved getting the ids into jinja in the html doc/


    #catches error, if user doesnt have enough top tracks or a top artist. it just displays nothing - catching the error is easier than checking the db
    try:
        artists = str([artist["external_urls"]["spotify"].split("artist")[1][1:] for artist in top_artists])[1:-1]
    except:
        artists = ""
    try:
        track = top_tracks[0]["external_urls"]["spotify"].split("track")[1][1:]
    except:
        track = ""


    user = Users.query.filter_by(id=id).first()

    if not user:
        new_user = Users(id=id, top_track = track, top_artists = artists, profile_picture = profile_picture)
        db.session.add(new_user)

    else:
        #update current users stats anyway
        # this isnt working at the moment
        user.top_track = track
        user.top_artists = artists
        user.profile_picture = profile_picture

    db.session.commit()

    return redirect(url_for("profile",user_id=id))






#home page route - atm doesnt do anything
@app.route("/home")
@app.route("/")
def home():
    id = check_login()


    return render_template("home.html", id = id)


#profile page route, atm displays some simple user stats fetched from API
@app.route("/profile/<user_id>")
def profile(user_id):
    id = check_login()




    user = Users.query.filter_by(id = user_id).first()
    if not user:
        return redirect(url_for("home"))
    top_track = user.top_track
    top_artists = str(user.top_artists).split(",")
    profile_picture = user.profile_picture
    followed_users = Follows.query.filter_by(follower_user_id=user_id).all()

    #check if following this user
    following_user = ""
    if id:
        following_user = Follows.query.filter_by(follower_user_id = id, followed_user_id = user_id).first()



    return render_template("profile.html",top_track = top_track, top_artists=top_artists, followed_users=followed_users,profile_picture = profile_picture,user_id=user_id,following_user = following_user,Users=Users ,id = id)


@app.route("/follow/<following_id>")
def follow(following_id):
    id = check_login()
        #check if refresh needed
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))
    sp = spotipy.Spotify(auth=token_info["access_token"])
    follower_id = sp.current_user()["id"]

    #checking if user exists or already follow user or following self
    existing_user = Users.query.filter_by(id=following_id).first()
    following_user = Follows.query.filter_by(follower_user_id = follower_id, followed_user_id = following_id).first()
    if following_user:
        db.session.delete(following_user)
    if existing_user and not following_user and following_id != follower_id:
        new_follows = Follows(follower_user_id = follower_id, followed_user_id = following_id)
        db.session.add(new_follows)

    #else there is an error
    db.session.commit()
    return redirect(url_for("profile", user_id =following_id))


@app.route("/reviews")
def reviews():
    id = check_login()
    return render_template("reviews.html", id = id)



@app.route("/articles")
def articles():
    id = check_login()
    return render_template("articles.html", id = id)

if __name__ == "__main__":
    app.run(debug=True)
