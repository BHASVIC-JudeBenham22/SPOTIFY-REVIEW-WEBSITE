from flask import Flask, render_template, redirect, url_for, request, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
#from .models import Users, Follows
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from sqlalchemy.orm import relationship
import time


app = Flask(__name__)


#making database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class Users(db.Model):
    id = db.Column(db.String, primary_key=True)

class Follows(db.Model):
    follower_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False, primary_key=True)
    followed_user_id = db.Column(db.Integer, ForeignKey('users.id'), nullable=False, primary_key=True)
    follower_user = db.relationship("Users", foreign_keys=[follower_user_id])
    followed_user = db.relationship("Users", foreign_keys=[followed_user_id])

db.create_all()


#inclue secret key so we can later use "sessions" to store spotify data
#we store all token info in the session
app.secret_key = "secretforsessions"

#all the paramaters we pass to spotify to allow me to use API
SpotifyOAuthData = SpotifyOAuth(
    client_id = "95cb7a03a44d445a9c83024b2cb2dab0",
    client_secret = "096f41ea16c545318fc53b15c50c90e4",
    redirect_uri = "http://127.0.0.1:5000/callback",
    scope = "user-top-read user-read-private user-read-email"
)

#to keep user logged in, the access token must be refreshed, this is done periodically and automatically
#every time this function is called, we check if the token is expired - if it is, then we refresh it
def refresh_token():
    token_info = session.get("token_info", None)
    if not session["token_info"]:
        redirect(url_for("login"))
    if token_info["expires_at"] < 60 + int(time.time()):
        token_info = SpotifyOAuthData.refresh_access_token(token_info["refresh_token"])
    return token_info

#if the user is not logged in, there will be no token in the session as only logged in users have this.
def check_login():
    if "token_info" in session:
        return True
    else: return False

#redirects user to spotify login prompt
@app.route("/login")
def login():
    auth_url = SpotifyOAuthData.get_authorize_url()
    return redirect(auth_url)

#final of oath2 flow, allows us to save token info to session for later use
@app.route("/callback")
def callback():
    session.clear()
    token_info = SpotifyOAuthData.get_access_token(request.args.get("code"))
    session["token_info"] = token_info


    #if user hasnt logged in before, save them to our users database
    #this may randomly break no idea why
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))
    sp = spotipy.Spotify(auth=token_info["access_token"])
    id = sp.current_user()["id"]
    user = Users.query.filter_by(id=id).first()
    if not user:
        new_user = Users(id=id)
        db.session.add(new_user)
        db.session.commit()

    return redirect(url_for("profile"))






#home page route - atm doesnt do anything
@app.route("/home")
@app.route("/")
def home():
    logged_in = check_login()

    return render_template("home.html", logged_in = logged_in)


#profile page route, atm displays some simple user stats fetched from API
@app.route("/profile")
def profile():
    logged_in = check_login()
    #check if refresh needed
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))



    #allows us to speak to api
    sp = spotipy.Spotify(auth=token_info["access_token"])

    top_artists = sp.current_user_top_artists(limit=50, time_range="medium_term")["items"]
    top_tracks = sp.current_user_top_tracks(limit=50, time_range="medium_term")["items"]
    id = sp.current_user()["id"]
    #ids for artists
    artists = [artist["external_urls"]["spotify"].split("artist")[1][1:] for artist in top_artists]
    tracks = [track["external_urls"]["spotify"].split("track")[1][1:] for track in top_tracks]

    return render_template("profile.html", artists = artists, tracks=tracks, logged_in = logged_in)


@app.route("/follow/<following_id>")
def follow(following_id):
    logged_in = check_login()
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
    if existing_user and not following_user and following_id != follower_id:

        new_follows = Follows(follower_user_id = follower_id, followed_user_id = following_id)
        db.session.add(new_follows)
        db.session.commit()
    #else there is an error

    return redirect(url_for("profile"))


@app.route("/reviews")
def reviews():
    return redirect(url_for("home"))



@app.route("/articles")
def articles():
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
