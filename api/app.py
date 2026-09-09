# -*- coding: utf-8 -*-
import json
import os
import pymysql
#from fastapi import FastAPI, HTTPException
from fastapi import FastAPI, HTTPException, Query
from openai import OpenAI

#from envia_alerta import *


MODE = os.getenv("REBEC_API_MODE", "DEV").upper()

# Credenciais nunca devem ficar hardcoded no repositório.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

config = {
    "mysql_host": os.getenv("REBEC_MYSQL_HOST", "127.0.0.1"),
    "mysql_port": int(os.getenv("REBEC_MYSQL_PORT", "3306")),
    "mysql_user": os.getenv("REBEC_MYSQL_USER", ""),
    "mysql_password": os.getenv("REBEC_MYSQL_PASSWORD", ""),
    "mysql_db": os.getenv("REBEC_MYSQL_DATABASE", ""),
}

db_config = {
        "host": config["mysql_host"],
        "user": config["mysql_user"],
        "password": config["mysql_password"],
        "database": config["mysql_db"],
        "cursorclass": pymysql.cursors.DictCursor
    }

def get_connection():
        return pymysql.connect(**db_config)

def fetch_one(query, params=()):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()

def fetch_all(query, params=()):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

def ask_rebeca(prompt_text, prompt_model):
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    response = client.chat.completions.create(
        model=prompt_model,#"gpt-4o",  # ou gpt-3.5-turbo
        messages=[
            {
                "role": "system",
                "content": "Você é um especialista em revisão de ensaios clínicos. Compare informações extraídas de pareceres com registros na plataforma."
            },
            {
                "role": "user",
                "content": prompt_text
            }
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content

def ensaios_recrutando():
    query = f"""
                SELECT 
                    s.inclusion_criteria,
                    s.public_title,
                    s.inclusion_criteria_pt,
                    s.public_title_pt,
                    s.url,
                    s.recruitment_status
                FROM search_source s
                WHERE LOWER(s.recruitment_status) IN ('recruiting', 'not yet recruiting');
            """
    ensaios_recrutando = fetch_all(query)
    return ensaios_recrutando

def ask_rebeca_recrutando(dado_voluntario, query_result):
    ensaios_recrut = ensaios_recrutando()

    prompt = '''
               Você é um especialista em pesquisa clinica, baseado no resultado da 
               query abaixo, avalie os campos inclusion_criteria e inclusion_criteria_pt
               para verificar se algum ensaio clinico é adequado para se voluntariar de acordo
               com o dado passado pelo voluntario.

               dado passado pelo voluntario: %s

               query com todos ensaios recrutando: %s

               retornar um json com:

               titulo publico em portugues e ingles
               url do ensaio
             ''' % (dado_voluntario, query_result)
    
    return ask_rebeca(prompt, "gpt-4o")#"gpt-3.5-turbo")

def get_trial_info(trial_id, config):
    db_config = {
        "host": config["mysql_host"],
        "user": config["mysql_user"],
        "password": config["mysql_password"],
        "database": config["mysql_db"],
        "cursorclass": pymysql.cursors.DictCursor
    }

    def get_connection():
        return pymysql.connect(**db_config)

    def fetch_one(query, params=()):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()

    def fetch_all(query, params=()):
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

    trial = fetch_one("SELECT * FROM repository_clinicaltrial WHERE id = %s", (trial_id,))
    if not trial:
        return None

    sponsor = fetch_one("SELECT * FROM repository_institution WHERE id = %s", (trial["primary_sponsor_id"],))
    
    contact_types = [
        "repository_publiccontact", "repository_scientificcontact",
        "repository_sitecontact", "repository_ethicsreviewcontact"
    ]
    contacts = {t: fetch_one(f"""
        SELECT c.* FROM {t} rel
        JOIN repository_contact c ON rel.contact_id = c.id
        WHERE rel.trial_id = %s
    """, (trial_id,)) for t in contact_types}

    attachments = fetch_all("""
        SELECT * FROM reviewapp_attachment att
        JOIN reviewapp_submission sub ON att.submission_id = sub.id
        WHERE sub.trial_id = %s
    """, (trial_id,))
    
    attach_qty = fetch_one("""
        SELECT COUNT(*) AS attach_qty FROM reviewapp_attachment att
        JOIN reviewapp_submission sub ON att.submission_id = sub.id
        WHERE sub.trial_id = %s
    """, (trial_id,))["attach_qty"]
    
    vocab_queries = {
        "study_type": "vocabulary_studytype",
        "study_purpose": "vocabulary_studypurpose",
        "intervention_assignment": "vocabulary_interventionassigment",
        "study_masking": "vocabulary_studymasking",
        "study_allocation": "vocabulary_studyallocation",
        "study_phase": "vocabulary_studyphase",
        "recruitment_status": "vocabulary_recruitmentstatus",
        "time_perspective": "vocabulary_timeperspective",
        "observational_study_design": "vocabulary_observationalstudydesign",
        "ipd_plan": "vocabulary_ipd_plan"
    }
    
    vocab_data = {}
    for key, table in vocab_queries.items():
        field = key.replace("study_", "") + "_id"
        if field in trial:
            result = fetch_one(f"SELECT label FROM {table} WHERE id = %s", (trial[field],))
            vocab_data[key] = result if result else None
    
    return {
        "clinical_trial": trial,
        "sponsor": sponsor,
        "contacts": contacts,
        "attachments": attachments,
        "attach_qty": attach_qty,
        "vocabulary": vocab_data
    }



# Conectar ao banco de dados MySQL usando PyMySQL
def get_db_connection():
    return pymysql.connect(
        host=config["mysql_host"],
        user=config["mysql_user"],
        password=config["mysql_password"],
        database=config["mysql_db"],
        cursorclass=pymysql.cursors.DictCursor  # Retorna os resultados como dicionário
    )



def user_admin(command,parametro):
    # Conectar ao banco de dados MySQL
    conn = mysql.connector.connect(
        host=HOST_DB,
        user=USER_DB,
        password=PASS_DB,
        database=NAME_DB
    )

    # Criar um cursor para executar a consulta
    cursor = conn.cursor(dictionary=True)


    connection = get_db_connection()
    cursor = connection.cursor()

    base_query = """
              SELECT
                       au.id, 
                au.first_name,
                au.last_name,
                au.email,
                au.last_login,
                au.username,
                au.is_active
                FROM 
                auth_user au
                WHERE where_clause = "au.username = '%s' or au.email = '%s'"
             """  % (parametro,parametro) 

    # Sua consulta SQL
    #if command in ["senha_emergencia","envia_username", "ativa_usuario"]:
    #    where_clause = "au.username = '%s' or au.email = '%s'" % (parametro,parametro)
    #    query = base_query % where_clause
    
        
        
    # Executar a consulta
    cursor.execute(query)
    
    MSG_FINAL = ""
    
    MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, "Informações do Usuário")
    for row in cursor.fetchall():
        user_id = row['id']
        user_mail = row['email']
        user_name = row['username']
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"User ID: {row['id']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"First Name: {row['first_name']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"Last Name: {row['last_name']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"Email: {row['email']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"Username: {row['username']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"Last Login: {row['last_login']}")
        MSG_FINAL = concatena_com_quebra_linha(MSG_FINAL, f"Is_active: {row['is_active']}")	    
        
    if command == "senha_emergencia":

        query = "update auth_user set password = 'tstetetet' where id = %s" % user_id
        print(query)
        #executa query
        emergency_hash = os.getenv("REBEC_EMERGENCY_PASSWORD_HASH", "")
        emergency_password = os.getenv("REBEC_EMERGENCY_PASSWORD", "")
        if not emergency_hash or not emergency_password:
            raise RuntimeError(
                "Emergency password is not configured. "
                "Set REBEC_EMERGENCY_PASSWORD_HASH and REBEC_EMERGENCY_PASSWORD."
            )
        cursor.execute(query, (emergency_hash, user_id))
        #cursor.commit()
        
        #envia infos de usuario e senha
        MSG_FINAL = concatena_com_quebra_linha(
            MSG_FINAL,
            "Password: %s" % os.getenv("REBEC_EMERGENCY_PASSWORD", "")
        )
        envia_alerta(MSG_FINAL, user_mail, "infos do usuario %s" % user_name)
        
    if command == "envia_username":
        #envia infos do usuario
        envia_alerta(MSG_FINAL, user_mail, "infos do usuario %s" % user_name)
        
    if command == "ativa_usuario":
        query = "update auth_user set is_active = 1 where id = %s" % user_id
        cursor.execute(query)
        cursor.commit()
        #envia infos do usuario
        query = "select * from auth_user where id = %s" % user_id
        cursor.execute(query)
        row = cursor.fetchall()[0]
        MSG_FINAL = user_info(row)
        envia_alerta(MSG_FINAL, user_mail, "Usuario %s ativado" % user_name)
    
    connection.close()



'''
def ask_rebeca(prompt_text):
    # Cria uma nova thread
    thread = client.beta.threads.create()

    # Adiciona a mensagem do usuário
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=prompt_text
    )

    # Inicia o processamento com o assistente
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID,
    )

    # Aguarda até o processamento ser concluído
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status in ["failed", "cancelled", "expired"]:
            raise Exception(f"Run falhou com status: {run_status.status}")
        time.sleep(1)

    # Recupera a resposta
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    resposta = messages.data[0].content[0].text.value

    return resposta
'''

# Criar o app FastAPI
app = FastAPI()

@app.get("/trial_info/{trial_id}")
async def trial_info(trial_id: str):
    print("####\nentrou em trial_info")
    print("trial_id: %s" % trial_id)
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = 'select creator_id, trial_id from reviewapp_submission where trial_id = (select id from repository_clinicaltrial where id = "%s" or trial_id = "%s")' % (trial_id, trial_id)
            print("query: %s" % query) 
            cursor.execute(query)
            result = cursor.fetchone()
            id_from_trial = result["trial_id"]
            print("result creator: %s" % result)
            query_username = "select username from auth_user where id = %s"
            cursor.execute(query_username, (result["creator_id"],))
            result = cursor.fetchone()
            print(result)
        
        connection.close()
        if result:
            username = result["username"]
            print("username---> %s" % username)

            # Chama internamente a função user_info
            user_data = await user_info(username)

        
            for trial in user_data["trials_from_user"][:]:
                print(trial.keys())
                trial_on_dic = list(trial.keys())[0]
                print("%s   ----    %s" % (trial_on_dic, trial_id))
                if trial_on_dic != id_from_trial:
                    user_data["trials_from_user"].remove(trial)



            return user_data
        else:
            raise HTTPException(status_code=404, detail="Trial not found")

    except pymysql.MySQLError as err:
        raise HTTPException(status_code=500, detail=f"MySQL error: {err}")

@app.get("/user_info/{user_ident}")
async def user_info(user_ident: str):
    print("####\nentrou em user_info")
    print("user_ident: %s" % user_ident)
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = "SELECT * FROM auth_user WHERE username like %s or email like %s"
            print("query: %s" % query) 
            cursor.execute(query, (user_ident,user_ident))
            result = cursor.fetchone()
            user_details = result

            #query to get trials from user
            query_trials_from_user = "select trial_id from reviewapp_submission where creator_id = %s" % user_details["id"]
            cursor.execute(query_trials_from_user)
            result = cursor.fetchall()
            trials_from_user = [{int(r["trial_id"]): {"history":[]}} for r in result]

            #query to get rbr
            query_rbr = "select trial_id from repository_clinicaltrial where id = %s"
            for trial in trials_from_user:
                print(trial.keys())
                trial_id = next(iter(trial.keys()))
                cursor.execute(query_rbr, (trial_id,))
                result = cursor.fetchone()
                trial[trial_id]["rbr"] = result["trial_id"]
            

            #query to get flux of trial
            query_flux = '''
                         SELECT submit_date AS date, 'SUBMIT FROM USER' AS action 
                          FROM picolo_submit 
                          WHERE trial_id = %s

                          UNION ALL

                         SELECT resubmit_date AS date, 'RESUBMIT FROM REVISOR' AS action 
                          FROM picolo_resubmit 
                          WHERE trial_id = %s

                          UNION ALL

                         SELECT approved_date AS date, 'APPROVED FROM REVISOR' AS action 
                         FROM picolo_approved 
                         WHERE trial_id = %s

                        ORDER BY date;
                      '''
            for trial in trials_from_user:
                print(trial.keys())
                trial_id = next(iter(trial.keys()))
                cursor.execute(query_flux, (trial_id,trial_id, trial_id))
                result = cursor.fetchall()
                for r in result:
                    trial[trial_id]["history"].append(r)
                #http://localhost:8000/user_info/nathypenaforte





        connection.close()

        #if result:
        return {"user_ident": user_ident, "user_details": user_details, "trials_from_user": trials_from_user}
        #else:
        #    raise HTTPException(status_code=404, detail="Trial not found")

    except pymysql.MySQLError as err:
        raise HTTPException(status_code=500, detail=f"MySQL error: {err}")


from fastapi.responses import JSONResponse

        
        
@app.get("/recruiting_trials")
async def recruiting_trials(search_token: str = Query(..., min_length=1, description="Search term for inclusion criteria")):
    try:
        # Normaliza o dado do voluntário
        search_token = search_token.lower()

        # Recupera todos os ensaios que estão recrutando
        recrut_trials = ensaios_recrutando()

        if not recrut_trials:
            raise HTTPException(status_code=404, detail="Nenhum ensaio clínico em recrutamento encontrado.")

        # Chama a função que avalia o melhor ensaio com base no dado do voluntário
        recomendacao = ask_rebeca_recrutando(dado_voluntario=search_token, query_result=recrut_trials)

        return JSONResponse(content={"recomendacao": recomendacao}, media_type="application/json; charset=utf-8")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/all_trial_info/{trial_id}")
async def all_trial_info(trial_id: str, username: str, token: str):
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Verificar se o usuário é staff ou superuser
            user_query = "SELECT is_staff, is_superuser FROM auth_user WHERE username = %s"
            cursor.execute(user_query, (username,))
            user = cursor.fetchone()

            if not user or (user["is_staff"] == 0 and user["is_superuser"] == 0):
                raise HTTPException(status_code=403, detail="Not authorized user")

            if token != "rebecarevisora":
                raise HTTPException(status_code=403, detail="Invalid token")

        connection.close()
        
        # Utilizando a função get_trial_info para obter as informações do ensaio clínico
        trial_data = get_trial_info(trial_id, config)
        
        if trial_data:
            return trial_data
        else:
            raise HTTPException(status_code=404, detail="Trial not found")

    except pymysql.MySQLError as err:
        raise HTTPException(status_code=500, detail=f"MySQL error: {err}")


