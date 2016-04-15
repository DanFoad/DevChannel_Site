import json

import flask
import requests

import server_config
from apps import invite, database, article

app = flask.Flask(__name__)
app.secret_key = server_config.SERVER_SECRET


@app.route('/')
@app.route('/index')
def index():
    articles = [article.Article(**params)for params in article.get_articles()]
    return flask.render_template('index.html', articles=reversed(articles))


@app.route('/docs')
def docs():
    return flask.render_template('docs.html')


@app.route('/about')
def about():
    return flask.render_template('about.html')


@app.route('/resources')
def resources():
    return flask.render_template('resources.html')


@app.route('/join', methods=['GET', 'POST'])
def join():
    if flask.request.method == 'POST':
        email = flask.request.form['email']
        skills = flask.request.form['skills']

        # redir: -1, 0 or 1
        # -1: stay on page;    0: redirect to index.html;    1: redirect to slack
        if email == '' or skills == '':
            redir, resp = -1, 'Please fill every field!'
        else:
            redir, resp = invite.send_invite(email, skills)

        return flask.render_template('join.html', status=redir, rep_error=resp)
    else:
        return flask.render_template('join.html', status=None, rep_error=None)


@app.route('/_database', methods=['GET', 'POST', 'PUT', 'DELETE'])
def _database():
    if flask.session.get('username') not in server_config.ALLOWED_USERS:
        flask.abort(403)

    args = {var_name: flask.request.args.get(var_name, '')
            for var_name in ('email', 'username', 'slack_id', 'github', 'skills', 'timezone', 'points')}

    if flask.request.method == 'POST':
        return database.insert_user(email=args['email'], username=args['username'], slack_id=args['slack_id'],
                                    skills=args['skills'], github=args['github'], timezone=args['timezone'],
                                    points=args['points'])

    elif flask.request.method == 'PUT':
        params = {var_name: args[var_name]
                  for var_name in ('skills', 'github', 'timezone', 'slack_id', 'username', 'email', 'points')
                  if args[var_name] != ''}

        return database.update_user(email=args['email'], username=args['username'], slack_id=args['slack_id'],
                                    params=params)

    elif flask.request.method == 'GET':
        if flask.request.args.get('req_all') == 'true':
            return database.get_all_users()
        return database.get_user(email=args['email'], username=args['username'], slack_id=args['slack_id'])

    elif flask.request.method == 'DELETE':
        return database.delete_user(email=args['email'], username=args['username'], slack_id=args['slack_id'])


@app.route('/_login')
def login():
    uri = 'https://github.com/login/oauth/authorize' \
          '?client_id={}'.format(server_config.GIT_CLIENT_ID)
    return flask.redirect(uri, code=302)


@app.route('/_callback')
def auth():
    session_code = flask.request.args.get('code', '')

    if session_code != '':
        resp = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': server_config.GIT_CLIENT_ID,
                'client_secret': server_config.GIT_CLIENT_SECRET,
                'code': session_code
            },
            headers={
                'accept': 'application/json'
            }
        )
        if resp.status_code == 200:
            resp = json.loads(resp.text)
            acc_info = requests.get('https://api.github.com/user',
                                    params={'access_token': resp.get('access_token')})
            if acc_info.status_code == 200:
                acc_info = json.loads(acc_info.text)
                flask.session['username'] = acc_info.get('login')

            return flask.redirect(flask.url_for('index'))

    return 'Something went wrong'


@app.route('/_upload', methods=['GET', 'POST'])
def _upload():
    if flask.session.get('username') not in server_config.ALLOWED_USERS:
        flask.abort(403)

    if flask.request.method == 'POST':
        author = flask.request.form['author']
        text = flask.request.form['text']
        text = parse(text)
        article.save_article(article.Article(author, text))
        return 'Done'
    return flask.render_template('_upload.html')


def parse(txt):
    txt = txt.split('\r\n')
    resp = ['']
    for line in txt:
        if line.startswith('    '):
            if isinstance(resp[-1], str):
                resp.append([line[4:]])
            else:
                resp[-1].append(line[4:])
        else:
            if isinstance(resp[-1], list):
                resp.append(line)
            else:
                resp[-1] += '\n' + line
    return resp


@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
def page_not_found(error):
    if str(error).startswith('403'):
        return flask.render_template('errors/403.html'), 403
    elif str(error).startswith('404'):
        return flask.render_template('errors/404.html'), 404
    elif str(error).startswith('500'):
        return flask.render_template('errors/500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)