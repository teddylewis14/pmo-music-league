from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)

def get_db_connection():
    """Get connection to the database"""
    conn = sqlite3.connect('music_league.db')
    conn.row_factory = sqlite3.Row  # This lets us access columns by name
    return conn

@app.route('/')
def index():
    """Home page showing all songs"""
    return render_template('index.html')

@app.route('/api/songs')
def get_songs():
    """API endpoint to get songs data with pagination"""
    conn = get_db_connection()
    
    # Get search and pagination parameters
    search = request.args.get('search', '')
    season = request.args.get('season', '')
    round_id = request.args.get('round', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))  # 50 songs per page
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Build the count query first
    count_query = """
        SELECT COUNT(*) as total
        FROM submissions s
        JOIN competitors c ON s.submitter_id = c.id
        JOIN rounds r ON s.round_id = r.id
        WHERE 1=1
    """
    
    count_params = []
    
    # Add search filter to count
    if search:
        count_query += " AND (s.title LIKE ? OR s.artist LIKE ? OR c.name LIKE ? OR r.name LIKE ?)"
        search_term = f"%{search}%"
        count_params.extend([search_term, search_term, search_term, search_term])
    
    # Add season filter to count
    if season:
        count_query += " AND r.season = ?"
        count_params.append(season)
    
    # Add round filter to count
    if round_id:
        count_query += " AND r.id = ?"
        count_params.append(round_id)
    
    # Get total count
    total_results = conn.execute(count_query, count_params).fetchone()['total']
    
    # Build the main query with pagination
    query = """
        SELECT 
            s.id as submission_id,
            s.title,
            s.artist,
            s.album,
            c.name as submitter,
            r.name as round_name,
            r.season,
            r.playlist_url,
            s.created,
            s.comment,
            s.spotify_uri,
            COUNT(v.points_assigned) as vote_count,
            COALESCE(SUM(v.points_assigned), 0) as total_points
        FROM submissions s
        JOIN competitors c ON s.submitter_id = c.id
        JOIN rounds r ON s.round_id = r.id
        LEFT JOIN votes v ON s.spotify_uri = v.spotify_uri AND v.round_id = r.id
        WHERE 1=1
    """
    
    params = []
    
    # Add search filter
    if search:
        query += " AND (s.title LIKE ? OR s.artist LIKE ? OR c.name LIKE ? OR r.name LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term, search_term])
    
    # Add season filter
    if season:
        query += " AND r.season = ?"
        params.append(season)
    
    # Add round filter
    if round_id:
        query += " AND r.id = ?"
        params.append(round_id)
    
    query += """
        GROUP BY s.id, s.title, s.artist, s.album, c.name, r.name, r.season, r.playlist_url, s.created, s.comment, s.spotify_uri
        ORDER BY s.created DESC
        LIMIT ? OFFSET ?
    """
    
    params.extend([per_page, offset])
    
    songs = conn.execute(query, params).fetchall()
    conn.close()
    
    # Convert to list of dictionaries
    songs_list = []
    for song in songs:
        # Convert Spotify URI to URL
        spotify_url = ""
        if song['spotify_uri']:
            # Convert spotify:track:ID to https://open.spotify.com/track/ID
            spotify_id = song['spotify_uri'].replace('spotify:track:', '')
            spotify_url = f"https://open.spotify.com/track/{spotify_id}"
        
        songs_list.append({
            'submission_id': song['submission_id'],
            'title': song['title'],
            'artist': song['artist'],
            'album': song['album'],
            'submitter': song['submitter'],
            'round_name': song['round_name'],
            'season': song['season'],
            'playlist_url': song['playlist_url'],
            'spotify_url': spotify_url,
            'created': song['created'],
            'comment': song['comment'] or '',
            'vote_count': song['vote_count'],
            'total_points': song['total_points'],
            'spotify_uri': song['spotify_uri']
        })
    
    # Calculate pagination info
    total_pages = (total_results + per_page - 1) // per_page
    
    return jsonify({
        'songs': songs_list,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_results': total_results,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    })

@app.route('/api/rounds')
def get_rounds():
    """API endpoint to get rounds for filtering"""
    conn = get_db_connection()
    
    # Get optional season filter
    season = request.args.get('season', '')
    
    query = "SELECT id, name, season FROM rounds WHERE 1=1"
    params = []
    
    if season:
        query += " AND season = ?"
        params.append(season)
    
    query += " ORDER BY season, created"
    
    rounds = conn.execute(query, params).fetchall()
    conn.close()
    
    rounds_list = []
    for round_data in rounds:
        rounds_list.append({
            'id': round_data['id'],
            'name': round_data['name'],
            'season': round_data['season']
        })
    
    return jsonify(rounds_list)

@app.route('/api/stats')
def get_stats():
    """API endpoint to get database statistics"""
    conn = get_db_connection()
    
    # Get total counts
    total_songs = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    total_competitors = conn.execute("SELECT COUNT(*) FROM competitors").fetchone()[0]
    total_rounds = conn.execute("SELECT COUNT(*) FROM rounds").fetchone()[0]
    total_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
    
    # Get seasons list
    seasons = conn.execute("SELECT DISTINCT season FROM rounds ORDER BY season").fetchall()
    seasons_list = [season['season'] for season in seasons]
    
    conn.close()
    
    return jsonify({
        'total_songs': total_songs,
        'total_competitors': total_competitors,
        'total_rounds': total_rounds,
        'total_votes': total_votes,
        'seasons': seasons_list
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)