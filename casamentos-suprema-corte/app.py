import os, sqlite3, secrets, json, requests
from datetime import date, datetime, timedelta
from functools import wraps
from io import BytesIO
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get('DATABASE_PATH', BASE / 'casamentos.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE') == '1'
DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '').strip()
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '').strip()
DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID', '').strip()
DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', '').strip()
# JSON: {"123456789012345678":"Ministro do Supremo","987654321098765432":"Juiz"}
try:
 DISCORD_ROLE_NAMES = json.loads(os.environ.get('DISCORD_ROLE_NAMES', '{}'))
 if not isinstance(DISCORD_ROLE_NAMES, dict): DISCORD_ROLE_NAMES = {}
except json.JSONDecodeError:
 DISCORD_ROLE_NAMES = {}
DISCORD_ALLOWED_ROLE_IDS = set(filter(None, (v.strip() for v in os.environ.get('DISCORD_ALLOWED_ROLE_IDS', '').split(','))))
DISCORD_API = 'https://discord.com/api/v10'


PACKAGES = {
 'ouro': {'name':'Ouro', 'description':'Cerimônia essencial com juiz de paz e certidão personalizada.', 'items':['Juiz de Paz para a cerimônia', 'Certidão de casamento personalizada']},
 'platina': {'name':'Platina', 'description':'Casamento completo e sofisticado, com comodidade para os convidados.', 'items':['Local para cerimônia (3 opções)', 'Juiz de Paz', 'Convites (4 modelos)', 'Música ambiente personalizada', 'Limousine para entrada dos noivos', 'Ônibus para convidados até a festa']},
 'diamante': {'name':'Diamante', 'description':'Celebração exclusiva, organizada sob medida.', 'items':['Local exclusivo para cerimônia e festa', 'Organização completa e DJ', 'Juiz de Paz', 'Convite totalmente personalizado', 'Seguranças do Jurídico', 'Equipe técnica de som', 'Limousine de luxo para a noiva', 'Cobertura fotográfica ampliada']}
}
STATUSES = ('Solicitado','Em análise','Aprovado','Recusado','Concluído')

def connect():
 DB.parent.mkdir(parents=True, exist_ok=True)
 con = sqlite3.connect(DB)
 con.row_factory = sqlite3.Row
 return con

def init_db():
 with connect() as con:
  con.execute('''CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)''')
  con.execute('''CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, protocol TEXT UNIQUE NOT NULL, package TEXT NOT NULL, package_price TEXT NOT NULL, partner1 TEXT NOT NULL, partner1_id TEXT NOT NULL, partner2 TEXT NOT NULL, partner2_id TEXT NOT NULL, judge TEXT NOT NULL, judge_id TEXT NOT NULL, ceremony_date TEXT NOT NULL, ceremony_time TEXT NOT NULL, venue TEXT NOT NULL, invitation TEXT NOT NULL, music TEXT NOT NULL, notes TEXT NOT NULL, contact TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Solicitado', created_at TEXT NOT NULL)''')

init_db()

def csrf_token():
 if 'csrf' not in session: session['csrf'] = secrets.token_urlsafe(32)
 return session['csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

@app.before_request
def verify_csrf():
 if request.method == 'POST' and not secrets.compare_digest(request.form.get('csrf',''), session.get('csrf','')):
  abort(400, 'Token de segurança inválido. Atualize a página.')

def admin_required(fn):
 @wraps(fn)
 def inner(*args, **kwargs):
  if not session.get('admin') and not session.get('discord_user'): return redirect(url_for('login'))
  return fn(*args, **kwargs)
 return inner

@app.route('/')
def index():
 return render_template('index.html', packages=PACKAGES, minimum=(date.today()+timedelta(days=3)).isoformat())

@app.route('/solicitar', methods=['POST'])
def submit():
 p = request.form
 pkg = p.get('package','')
 if pkg not in PACKAGES: abort(400, 'Pacote inválido')
 required = ['partner1','partner1_id','partner2','partner2_id','judge','judge_id','ceremony_date','ceremony_time','contact']
 if any(not p.get(k,'').strip() for k in required):
  flash('Preencha todos os campos obrigatórios.','error'); return redirect(url_for('index')+'#solicitar')
 try: ceremony = date.fromisoformat(p['ceremony_date'])
 except ValueError: abort(400, 'Data inválida')
 if ceremony < date.today()+timedelta(days=3):
  flash('Solicitações devem ser feitas com pelo menos 3 dias de antecedência.','error'); return redirect(url_for('index')+'#solicitar')
 try: datetime.strptime(p['ceremony_time'],'%H:%M')
 except ValueError: abort(400, 'Horário inválido')
 values = [p.get(k,'').strip()[:500] for k in ['partner1','partner1_id','partner2','partner2_id','judge','judge_id','ceremony_date','ceremony_time','venue','invitation','music','notes','contact']]
 price = os.environ.get('PRICE_'+pkg.upper(), 'A combinar')[:80]
 protocol = 'SCN-'+datetime.now().strftime('%Y%m%d')+'-'+secrets.token_hex(3).upper()
 with connect() as con:
  con.execute('''INSERT INTO requests(protocol,package,package_price,partner1,partner1_id,partner2,partner2_id,judge,judge_id,ceremony_date,ceremony_time,venue,invitation,music,notes,contact,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (protocol,pkg,price,*values,'Solicitado',datetime.now().isoformat(timespec='seconds')))
 return render_template('success.html', protocol=protocol)

def discord_configured():
 return all((DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_GUILD_ID, DISCORD_REDIRECT_URI, DISCORD_ALLOWED_ROLE_IDS))

@app.route('/auth/discord')
def discord_start():
 if not discord_configured():
  abort(503, 'Integração Discord ainda não configurada.')
 state = secrets.token_urlsafe(32)
 session['discord_oauth_state'] = state
 from urllib.parse import urlencode
 params = {'client_id': DISCORD_CLIENT_ID, 'redirect_uri': DISCORD_REDIRECT_URI,
           'response_type': 'code', 'scope': 'identify guilds.members.read', 'state': state}
 return redirect('https://discord.com/oauth2/authorize?' + urlencode(params))

@app.route('/auth/discord/callback')
def discord_callback():
 state = session.pop('discord_oauth_state', None)
 if not state or not secrets.compare_digest(state, request.args.get('state', '')):
  abort(400, 'Estado OAuth inválido. Tente novamente.')
 if request.args.get('error'):
  flash('Autorização do Discord cancelada.', 'error'); return redirect(url_for('login'))
 code = request.args.get('code', '')
 if not code: abort(400, 'Código de autorização ausente.')
 try:
  token_resp = requests.post(DISCORD_API + '/oauth2/token', data={
   'client_id': DISCORD_CLIENT_ID, 'client_secret': DISCORD_CLIENT_SECRET,
   'grant_type': 'authorization_code', 'code': code,
   'redirect_uri': DISCORD_REDIRECT_URI}, timeout=12)
  token_resp.raise_for_status()
  token = token_resp.json()['access_token']
  headers = {'Authorization': 'Bearer ' + token}
  user_resp = requests.get(DISCORD_API + '/users/@me', headers=headers, timeout=12)
  member_resp = requests.get(DISCORD_API + '/users/@me/guilds/' + DISCORD_GUILD_ID + '/member', headers=headers, timeout=12)
  if member_resp.status_code in (403, 404):
   flash('Você precisa participar do Discord oficial para acessar.', 'error'); return redirect(url_for('login'))
  user_resp.raise_for_status(); member_resp.raise_for_status()
  user = user_resp.json(); member = member_resp.json()
 except (requests.RequestException, KeyError, ValueError):
  flash('Não foi possível validar sua conta no Discord. Tente novamente.', 'error'); return redirect(url_for('login'))
 roles = set(map(str, member.get('roles', [])))
 authorized = roles & DISCORD_ALLOWED_ROLE_IDS
 if not authorized:
  flash('Seu cargo no Discord não tem permissão para acessar este painel.', 'error'); return redirect(url_for('login'))
 # Ordem de prioridade definida em DISCORD_ALLOWED_ROLE_IDS (primeiro cargo vence).
 role_id = next((r for r in os.environ.get('DISCORD_ALLOWED_ROLE_IDS','').split(',') if r.strip() in authorized), '')
 role_id = role_id.strip()
 name = member.get('nick') or (member.get('user') or {}).get('global_name') or user.get('global_name') or user.get('username', 'Usuário')
 avatar_hash = user.get('avatar')
 avatar = ('https://cdn.discordapp.com/avatars/' + str(user['id']) + '/' + avatar_hash + '.png') if avatar_hash else None
 session.clear()
 session['discord_user'] = {'id': str(user['id']), 'name': str(name)[:100],
                            'role_id': role_id, 'role': str(DISCORD_ROLE_NAMES.get(role_id, 'Cargo autorizado'))[:100], 'avatar': avatar}
 return redirect(url_for('dashboard'))

@app.route('/admin/setup', methods=['GET','POST'])
def setup():
 with connect() as con: exists=con.execute('SELECT 1 FROM admin LIMIT 1').fetchone()
 if exists: return redirect(url_for('login'))
 if request.method=='POST':
  username=request.form.get('username','').strip()
  password=request.form.get('password','')
  if len(username)<3 or len(password)<12:
   flash('Usuário: mínimo 3 caracteres. Senha: mínimo 12 caracteres.','error')
  else:
   with connect() as con: con.execute('INSERT INTO admin(username,password_hash) VALUES(?,?)',(username,generate_password_hash(password)))
   flash('Administrador criado. Faça login.','success'); return redirect(url_for('login'))
 return render_template('auth.html', mode='setup')

@app.route('/admin/login', methods=['GET','POST'])
def login():
 with connect() as con:
  if not con.execute('SELECT 1 FROM admin LIMIT 1').fetchone() and not discord_configured(): return redirect(url_for('setup'))
 if request.method=='POST':
  with connect() as con: admin=con.execute('SELECT * FROM admin WHERE username=?',(request.form.get('username',''),)).fetchone()
  if admin and check_password_hash(admin['password_hash'],request.form.get('password','')):
   session.clear(); session['admin']=admin['id']; return redirect(url_for('dashboard'))
  flash('Credenciais inválidas.','error')
 return render_template('auth.html', mode='login', discord_enabled=discord_configured())

@app.route('/admin/logout', methods=['POST'])
@admin_required
def logout():
 session.clear(); return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def dashboard():
 with connect() as con: rows=con.execute('SELECT * FROM requests ORDER BY id DESC').fetchall()
 return render_template('dashboard.html', rows=rows, packages=PACKAGES, statuses=STATUSES, discord_user=session.get('discord_user'))

@app.route('/admin/<int:request_id>/status', methods=['POST'])
@admin_required
def status(request_id):
 s=request.form.get('status','')
 if s not in STATUSES: abort(400)
 with connect() as con:
  cur=con.execute('UPDATE requests SET status=? WHERE id=?',(s,request_id))
  if not cur.rowcount: abort(404)
 flash('Situação atualizada.','success'); return redirect(url_for('dashboard'))

@app.route('/admin/<int:request_id>/pdf')
@admin_required
def pdf(request_id):
 with connect() as con: row=con.execute('SELECT * FROM requests WHERE id=?',(request_id,)).fetchone()
 if not row: abort(404)
 buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4); width,height=A4
 navy=colors.HexColor('#102641'); gold=colors.HexColor('#b9914b')
 c.setFillColor(navy); c.rect(0,height-115,width,115,fill=1,stroke=0)
 c.setFillColor(gold); c.setFont('Helvetica-Bold',18); c.drawCentredString(width/2,height-48,'SUPREMA CORTE NOBRE')
 c.setFillColor(colors.white); c.setFont('Helvetica',11); c.drawCentredString(width/2,height-75,'SOLICITACAO DE CASAMENTO • REGISTRO RP')
 y=height-155
 fields=[('Protocolo',row['protocol']),('Pacote',PACKAGES[row['package']]['name']),('Valor informado',row['package_price']),('Noivo(a) 1',row['partner1']+' | ID: '+row['partner1_id']),('Noivo(a) 2',row['partner2']+' | ID: '+row['partner2_id']),('Juiz de Paz',row['judge']+' | ID: '+row['judge_id']),('Data e hora',row['ceremony_date']+' as '+row['ceremony_time']),('Local',row['venue']),('Convite',row['invitation']),('Musica',row['music']),('Contato',row['contact']),('Observacoes',row['notes']),('Situacao',row['status'])]
 for label,value in fields:
  c.setFillColor(navy); c.setFont('Helvetica-Bold',10); c.drawString(45,y,label+':'); y-=17
  c.setFillColor(colors.HexColor('#333333')); c.setFont('Helvetica',10)
  for line in simpleSplit(str(value).encode('latin-1','replace').decode('latin-1') or '-', 'Helvetica',10,width-90):
   c.drawString(45,y,line); y-=15
  y-=9
  if y<75: c.showPage(); y=height-60
 c.setFillColor(gold); c.setFont('Helvetica',9); c.drawCentredString(width/2,38,'Documento de solicitacao. Nao equivale a certidao de casamento.')
 c.save(); buf.seek(0)
 return send_file(buf,mimetype='application/pdf',as_attachment=True,download_name=f'{row["protocol"]}.pdf')
@app.route('/diagnostico-discord')
def diagnostico_discord():
    nomes = [
        'DISCORD_CLIENT_ID',
        'DISCORD_CLIENT_SECRET',
        'DISCORD_GUILD_ID',
        'DISCORD_REDIRECT_URI',
        'DISCORD_ALLOWED_ROLE_IDS'
    ]

    faltando = [
        nome for nome in nomes
        if not os.environ.get(nome, '').strip()
    ]

    return {
        'discord_configurado': discord_configured(),
        'quantidade_variaveis_ausentes': len(faltando)
    }
if __name__=='__main__':
 app.run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
