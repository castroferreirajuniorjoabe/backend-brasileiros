import requests
url = "https://brasileiros-api.onrender.com/auth/login"
data = {"email": "consulado.marseille@brasileirosfranca.app", "password": "consulado123"}
r = requests.post(url, json=data)
if r.status_code == 200:
    token = r.json()["access_token"]
    post_url = "https://brasileiros-api.onrender.com/consulate/posts"
    post_data = {"title": "Test Edit Function", "description": "Descricao de teste para validar 10 chars", "category": "evento", "consulate": "marseille"}
    r2 = requests.post(post_url, json=post_data, headers={"Authorization": f"Bearer {token}"})
    print("CREATE:", r2.status_code, r2.text)
    if r2.status_code == 201:
        post_id = r2.json()["id"]
        put_url = f"https://brasileiros-api.onrender.com/consulate/posts/{post_id}"
        put_data = {"title": "Test Edit Edited", "description": "Descricao de teste para validar 10 chars", "category": "evento"}
        r3 = requests.put(put_url, json=put_data, headers={"Authorization": f"Bearer {token}"})
        print("PUT result:", r3.status_code, r3.text)
