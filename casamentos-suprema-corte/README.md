# Casamentos · Suprema Corte Nobre

Site independente para solicitação de casamentos RP, com pacotes Ouro, Platina e Diamante, prazo mínimo de 3 dias, IDs dos noivos e juiz de paz, painel administrativo e PDF de solicitação.

## Executar no Windows

1. Instale Python 3.10 ou superior.
2. Abra o terminal na pasta do projeto.
3. Execute:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

4. Abra http://127.0.0.1:5000/admin/setup e crie o administrador (senha com pelo menos 12 caracteres).
5. Acesse http://127.0.0.1:5000 para usar o site.

## Preços

Como os valores não foram informados, o site exibe 'A combinar'. Para definir os valores dos novos pedidos, configure as variáveis de ambiente `PRICE_OURO`, `PRICE_PLATINA`, `PRICE_DIAMANTE` antes de iniciar o aplicativo. Exemplo PowerShell:

```powershell
$env:PRICE_OURO='R$ 1.000.000'
$env:PRICE_PLATINA='R$ 2.000.000'
$env:PRICE_DIAMANTE='R$ 3.000.000'
python app.py
```

Esses valores são APENAS exemplos, não preços oficiais.

## Publicar no GitHub

Crie um repositório privado e envie os arquivos do projeto (não envie `.venv`, `.db` ou `.env`). O GitHub hospeda o código, não o servidor Flask. Para tornar o site público, use uma hospedagem Python com armazenamento persistente. Configure `SECRET_KEY` com valor secreto longo, `COOKIE_SECURE=1` sob HTTPS e `DATABASE_PATH` para um volume persistente. SQLite é indicado para uso pequeno; para múltiplos servidores, migre para PostgreSQL. Faça backup do banco.

## Observações

- Não há pagamento integrado nem confirmação automática de agenda.
- O PDF é um **comprovante de solicitação**, não uma certidão de casamento.
- O painel permite alterar status. Somente administradores autenticados podem acessar pedidos e PDFs.
- O prazo mínimo é verificado no servidor usando a data do servidor. Configure o fuso horário corretamente.
- Antes de uso público em produção, adicione limitação de requisições, proteção contra spam, auditoria e um fluxo de redefinição de senha.
