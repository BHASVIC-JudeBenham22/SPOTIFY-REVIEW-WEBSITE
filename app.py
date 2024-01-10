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


#making database
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
app.secret_key = "secretforsessions"

#all the paramaters we pass to spotify to allow me to use API
#added cache handler should make work for multiple users
cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)


SpotifyOAuthData = SpotifyOAuth(
    client_id = "95cb7a03a44d445a9c83024b2cb2dab0",
    client_secret = "096f41ea16c545318fc53b15c50c90e4",
    redirect_uri = "http://127.0.0.1:5000/callback",
    #redirect_uri = "https://7d48-81-109-105-102.ngrok-free.app/callback",
    scope = "user-top-read user-read-private user-read-email",
    cache_handler=cache_handler
)

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

#if the user is not logged in, there will be no token in the session as only logged in users have this.
def check_login():
    #added this just now for new cache system
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

    #issue above. all token info is the same dispite different "code"
    #i fixed this isssue now dw

    #session["token_info"] = token_info



    #if user hasnt logged in before, save them to our users database
    #this may randomly break no idea why
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
@app.route("/home", methods=["GET", "POST"])
@app.route("/",methods=["GET", "POST"])
def home():
    id = check_login()

    if request.method == "POST":
        search = request.form.get("search")
        if search:
            return redirect(url_for("search_results", search = search))

    return render_template("home.html", id = id)

@app.route("/search_results/<search>")
def search_results(search):
    id = check_login()
        #check if refresh needed
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))
    sp = spotipy.Spotify(auth=token_info["access_token"])

    search_results = sp.search(search)["tracks"]["items"]

    return render_template("search_results.html", id=id, search_results=search_results)


@app.route("/media/<media_id>")
def media(media_id):
    id = check_login()
        #check if refresh needed
    try:
        token_info = refresh_token()
    except:
        return redirect(url_for("home"))
    sp = spotipy.Spotify(auth=token_info["access_token"])


    #urn = f"{media_id}"
    artist = sp.album(media_id)["artists"][0]["external_urls"]["spotify"][32:]
    genres = sp.artist(artist)["genres"]





    return render_template("media.html", id=id, media_id=media_id, artist = artist, genres=genres)


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
