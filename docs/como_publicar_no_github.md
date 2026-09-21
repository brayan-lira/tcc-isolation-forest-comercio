# Como publicar este repositório no GitHub

Roteiro completo, do zero, para quem nunca usou o Git.

Sua conta: **https://github.com/brayan-lira**
Endereço final do repositório: **https://github.com/brayan-lira/tcc-isolation-forest-comercio**

---

## Antes de tudo: o TCC precisa ser corrigido

O texto do trabalho cita `github.com/brayanlira/...` — **sem o hífen**. Seu usuário real é `brayan-lira`, **com hífen**. Um leitor que digitar o endereço do TCC receberá página de erro, e o orientador cobrará novamente.

Na seção *Material e Métodos*, localize o trecho e corrija para:

> https://github.com/brayan-lira/tcc-isolation-forest-comercio

O `config/config.yaml` e o `CITATION.cff` deste pacote já estão com o endereço correto.

---

## 1. Criar o repositório vazio

1. Acesse <https://github.com/new>.
2. **Repository name:** `tcc-isolation-forest-comercio`
   (copie exatamente assim — o endereço é sensível a maiúsculas e hífens)
3. **Description:** `Pacote de reprodução do TCC — MBA USP/ESALQ Data Science e Analytics`
4. Selecione **Public**. O trabalho afirma que o repositório é público; se ficar privado, a banca não conseguirá abrir.
5. **Não marque** "Add a README file", "Add .gitignore" nem "Choose a license". Esses arquivos já existem neste pacote e a marcação causaria conflito no primeiro envio.
6. Clique em **Create repository**.

A página seguinte mostrará instruções do GitHub. Ignore-as e siga este roteiro.

---

## 2. Instalar o Git

Verifique se já está instalado:

```bash
git --version
```

Se aparecer "command not found", baixe em <https://git-scm.com/downloads> e instale com as opções padrão.

Configure sua identidade uma única vez:

```bash
git config --global user.name "Brayan Roberto Vieira Lira"
git config --global user.email "brayanroberto11@gmail.com"
```

Use o mesmo e-mail cadastrado na sua conta do GitHub, para que os envios apareçam vinculados ao seu perfil.

---

## 3. Preparar a autenticação

**A senha da conta não funciona mais.** Gere um token de acesso pessoal:

1. Acesse <https://github.com/settings/tokens>.
2. **Generate new token** → **Generate new token (classic)**.
3. **Note:** `TCC` · **Expiration:** 90 days.
4. Marque a caixa **`repo`** (isso habilita as subopções automaticamente).
5. **Generate token**.
6. **Copie o token imediatamente.** Ele aparece uma única vez. Guarde em local seguro.

Quando o Git pedir *Username*, digite `brayan-lira`. Quando pedir *Password*, **cole o token**.

---

## 4. Enviar o conteúdo

Descompacte este pacote, abra o terminal dentro da pasta `tcc-isolation-forest-comercio` e execute, uma linha por vez:

```bash
git init
git add .
git commit -m "Pacote de reprodução do TCC: coleta, indicadores, modelo e figuras"
git branch -M main
git remote add origin https://github.com/brayan-lira/tcc-isolation-forest-comercio.git
git push -u origin main
```

No `git push`, o Git pedirá usuário e senha. Use `brayan-lira` e o token.

> **Como saber se está na pasta certa?** Execute `ls` (ou `dir` no Windows). Devem aparecer `README.md`, `run_all.py`, `src`, `config`. Se aparecer apenas `tcc-isolation-forest-comercio`, entre nela com `cd tcc-isolation-forest-comercio`.

---

## 5. Conferir o que subiu

Abra <https://github.com/brayan-lira/tcc-isolation-forest-comercio> e verifique:

- [ ] O `README.md` aparece renderizado na página inicial.
- [ ] A pasta `src/` contém os nove arquivos `.py`.
- [ ] A pasta `data/raw/` está **vazia** (apenas `.gitkeep`). Os arquivos da CVM não devem subir.
- [ ] A licença MIT é reconhecida no painel lateral direito.
- [ ] O endereço na barra do navegador tem o hífen: `brayan-lira`.

Se algum arquivo grande subiu por engano:

```bash
git rm -r --cached data/raw
git commit -m "Remove arquivos brutos do versionamento"
git push
```

---

## 6. Após executar o protocolo com os dados reais

Quando rodar `python run_all.py` com os arquivos da CVM, envie as saídas geradas:

```bash
git add data/processed outputs/tables outputs/figures data/raw/proveniencia.csv
git commit -m "Adiciona base processada, tabelas, figuras e registro de proveniência"
git push
```

O arquivo `data/raw/proveniencia.csv` é importante: registra o tamanho e o código *hash* SHA-256 de cada arquivo baixado, permitindo identificar a versão exata dos dados diante de eventuais reapresentações.

---

## 7. Antes da defesa

**Marcar a versão avaliada.** Assim, ainda que o repositório evolua, a banca acessa exatamente o estado citado no trabalho:

```bash
git tag -a v1.0.0 -m "Versão apresentada na defesa"
git push origin v1.0.0
```

**Descrição e tópicos.** Na página do repositório, clique na engrenagem ao lado de *About*, preencha a descrição e adicione os tópicos: `auditoria`, `isolation-forest`, `anomaly-detection`, `cvm`, `usp-esalq`.

**Opcional — DOI permanente.** Conectar o repositório ao [Zenodo](https://zenodo.org) gera um DOI citável para a versão marcada, reforçando o argumento de reprodutibilidade na defesa.

---

## Problemas comuns

| Mensagem | Causa | Solução |
|---|---|---|
| `remote origin already exists` | O comando `remote add` foi executado duas vezes | `git remote set-url origin https://github.com/brayan-lira/tcc-isolation-forest-comercio.git` |
| `Authentication failed` | Usou a senha da conta | Use o token do passo 3 |
| `repository not found` | Nome digitado errado ou repositório ainda não criado | Confira o hífen em `brayan-lira` e refaça o passo 1 |
| `updates were rejected` | O repositório foi criado com README pelo site | `git pull origin main --allow-unrelated-histories` e depois `git push` |
| `src refspec main does not match any` | O `commit` não foi feito | Refaça `git add .` e `git commit -m "..."` |
