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
    Reviews = db.relationship("Reviews")
    Comments = db.relationship("Comments")

class Follows(db.Model):
    follower_user_id = db.Column(db.String, ForeignKey('users.id'), nullable=False, primary_key=True)
    followed_user_id = db.Column(db.String, ForeignKey('users.id'), nullable=False, primary_key=True)
    follower_user = db.relationship("Users", foreign_keys=[follower_user_id])
    followed_user = db.relationship("Users", foreign_keys=[followed_user_id])

class Reviews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.String)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    rating = db.Column(db.Integer, nullable = False)
    content = db.Column(db.String)
    Comments = db.relationship("Comments")

class Comments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    content = db.Column(db.String)


#use below code if running on repl.it
#with app.app_context():
#  db.create_all()

db.create_all()


#inclue secret key so we can later use "sessions" to store spotify data
#we store all token info in the session
app.secret_key = "secretforsessions"

#all the paramaters we pass to spotify to allow me to use API
#added cache handler should make work for multiple users
cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)


SpotifyOAuthData = SpotifyOAuth(
    client_id = "c8f7544ac8de4d0fa182466d1d87f2a7",
    client_secret = "61d6091fa94840b7b7383013295d471e",
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
        #check if refresh needed

    #try:
    #    token_info = refresh_token()
    #except:
    #    return redirect(url_for("home"))

    if id:

        token_info = refresh_token()

        sp = spotipy.Spotify(auth=token_info["access_token"])


    if request.method == "POST":
        search = request.form.get("search")
        if search:
            return redirect(url_for("search_results", search = search))

    #need to display recomended albums

    #get top top_artists
    #get the current_user_top_tracks
    #go in database

    recomendations = ""
    if id:
        user = Users.query.filter_by(id = id).first()
        top_artists = str(user.top_artists).split(",")
        top_track = [user.top_track]
        top_artists = [artist.strip()[1:-1] for artist in top_artists][0:2]

        genres = sp.artist(top_artists[0])["genres"]

        if genres == "" or genres == []:
            genres = ["pop"]
        else:
            genres = [sp.artist(top_artists[0])["genres"][0]]
        if top_artists == [] or top_artists == [""]:
            top_artists = ["06HL4z0CvFAxyc27GXpf02","3TVXtAsR1Inumwj472S9r4"]
        if top_track == [] or top_track == [""]:
            top_track = ["7LR85XLWw2yXqKBSI5brbG"]

        recomendations = sp.recommendations(seed_artists=top_artists, seed_genres=genres, seed_tracks=top_track, limit=10, country=None)
    #this returns songs, then need to get the albums


    return render_template("home.html", recomendations = recomendations ,id = id)

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

    albums = sp.artist_albums( artist, limit=3,)["items"]
    #[0]["external_urls"]["spotify"][31:]

    reviews = Reviews.query.filter_by(album_id = media_id).order_by(Reviews.id)




    return render_template("media.html", id=id, media_id=media_id, artist = artist, genres=genres, albums = albums, reviews = reviews)


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

    reviews = Reviews.query.filter_by(user_id = user_id).order_by(Reviews.id)


    return render_template("profile.html",top_track = top_track, top_artists=top_artists, followed_users=followed_users,profile_picture = profile_picture,user_id=user_id,following_user = following_user,Users=Users,reviews=reviews ,id = id)


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

    recent_reviews = Reviews.query.order_by(Reviews.id.desc()).limit(10).all()
    if id:
        followed_user_ids = []
        followed_users = Follows.query.filter_by(follower_user_id=id).all()
        for user in followed_users:
            followed_user_ids.append(user.followed_user_id)



        followed_users_reviews = Reviews.query.filter(Reviews.user_id.in_(followed_user_ids)).order_by(Reviews.id.desc()).limit(10).all()


    return render_template("reviews.html", id = id, recent_reviews = recent_reviews, followed_users_reviews = followed_users_reviews)

@app.route("/review/<review_id>")
def review(review_id):
    id = check_login()
    review = Reviews.query.filter_by(id = review_id).first()
    album_id = review.album_id
    content = review.content
    rating = review.rating
    user_id = review.user_id

    comments = Comments.query.filter_by(review_id=review_id).all()

    return render_template("review.html", id=id, content = content, rating = rating, user_id=user_id, album_id=album_id, comments = comments, review_id=review_id)

@app.route("/post/<album_id>", methods=['GET', 'POST'])
def post(album_id):
    id = check_login()
    if not id:
        return redirect(url_for("home"))
    if request.method == 'POST':
        content = request.form.get("content")
        #rating = request.form.get("rating")
        rating = 1
        user_id = id

        new_review = Reviews(content=content, rating=rating, user_id=user_id,album_id=album_id)
        db.session.add(new_review)
        db.session.commit()
        return redirect(url_for("media", media_id=album_id))
    return render_template("post.html", album_id=album_id)

    #return redirect(url_for("profile", user_id=id))

@app.route("/comment/<review_id>", methods=['GET', 'POST'])
def comment(review_id):
    id = check_login()
    review = Reviews.query.filter_by(id = review_id).first()
    if not id or not review:
        return redirect(url_for("home"))
    if request.method == "POST":
        content = request.form.get("content")

        user_id = id

        new_comment = Comments(content=content, user_id=user_id, review_id=review_id)
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("review",review_id=review_id))
    return render_template("comment.html", review_id=review_id)


@app.route("/articles")
def articles():
    id = check_login()
    return render_template("articles.html", id = id)

if __name__ == "__main__":
    app.run(debug=True)
