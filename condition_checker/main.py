from flask import Flask
import requests,os

app = Flask(__name__)

hdrnet_host = os.environ.get('HDRNET_HOST', '172.17.0.1')
hdrnet_port = os.environ.get('HDRNET_PORT', '8079')

@app.route('/check_condition')
def check_condition():
    # Assume condition_checker service is running on port 5001
    try:
        condition_result = requests.get('http://condition_checker:5001/get_condition')
        data = condition_result.json()
    except requests.exceptions.ConnectionError:
        print("Condition checker service is unavailable")
        return "Condition checker service is unavailable"
    if data['condition'] == 'cat':
        try:
            response = requests.get('http://service_1:5002/do_something')
            print(response)
        except requests.exceptions.ConnectionError:
            print("Service 1 is unavailable")
            return "Service 1 unavailable"
    elif data['condition'] == 'dog':
        try:
            response = requests.get('http://service_2:5003/do_something_else')   
            print(response)
        except requests.exceptions.ConnectionError:
            print("Service 2 is unavailable")
            return "Service 2 unavailable"
    else:  
        try:
            response = requests.get('http://localhost:5004/do_another_thing')
            print(response)
        except requests.exceptions.ConnectionError:
            print("Service 3 is unavailable")
            return "Service 3 unavailable"
    return response.text

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)