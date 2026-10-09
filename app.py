from dotenv import load_dotenv
from flask import Flask, request
import requests

load_dotenv()

from agents import manager_agent

#supportive functions
def custom_query(get_url, header):
    #print(get_url)
    try:
        r = requests.get(get_url, headers=header)
        return r.json()
    except Exception as e:
       print(e)
       return r


app = Flask(__name__)

@app.route('/', methods=['GET'])
#home page
def index():
    return 'Hello'

#called by a cronjob to wake up service
@app.route('/health', methods=['GET'])
def health():
    return {'result': 'ok'}
#
@app.route('/post_query_raw_url', methods=['POST'])
def get_raw_trip_details():
    if request.form.get('org_url') is None:
        return {'result': 'failed', 'message': 'Missing org_url'}
    try :
        rawDetails = custom_query(request.form.get('org_url'), 
                          {'Accept':'*/*', "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"})
        #print(rawDetails['nodes'][1])
        if 'nodes' in rawDetails:
            return rawDetails['nodes'][1]
    except Exception as e:
        print(e)
    return {'result': 'failed', 'message': 'Cannot get raw details'}

#multi-agent planner chatbot: {text, session_id} -> {result: 'OK', text}
@app.route('/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    text, session_id = body.get('text'), body.get('session_id')
    if not isinstance(text, str) or not text.strip() or not isinstance(session_id, str) or not session_id:
        return {'result': 'failed', 'message': 'Missing text or session_id'}, 400
    try:
        return {'result': 'OK', 'text': manager_agent.chat(session_id, text.strip())}
    except Exception as e:
        print(e)
        return {'result': 'failed', 'message': 'Chatbot unavailable'}, 500

#run the server: python3 app.py
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)   #run development configs -> remove this when releasing

   