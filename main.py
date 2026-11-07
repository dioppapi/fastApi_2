from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from fastapi.middleware.cors import CORSMiddleware


class LivreIn(BaseModel):                 # ce que le client envoie
    model_config = ConfigDict(str_strip_whitespace=True)
    titre: str = Field(min_length=1, max_length=200)
    auteur: str = Field(min_length=1, max_length=100)
    annee: int | None = Field(default=None, ge=1000, le=2100)

class Livre(LivreIn):                     # ce que l'API renvoie
    id: int
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query, status

DB = "biblio.db"

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS livre (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            titre  TEXT NOT NULL,
            auteur TEXT NOT NULL,
            annee  INTEGER)""")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                    # exécuté au démarrage du serveur
    yield

app = FastAPI(title="API Bibliothèque", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def get_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn               # donnée à l'endpoint
    finally:
        conn.close()             # toujours fermée, même en cas d'erreur

Db = Annotated[sqlite3.Connection, Depends(get_db)]
@app.get('/')
def accueil():
    return {'message':'Bonjour Atelier'}
#1- lire
def lire_ou_404(db: sqlite3.Connection, livre_id: int) -> dict:
    ligne = db.execute(
        "SELECT * FROM livre WHERE id = ?", (livre_id,)).fetchone()
    if ligne is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")
    return dict(ligne)
#2-  Ajouter livre
@app.post("/livres", response_model=Livre, status_code=status.HTTP_201_CREATED)
def creer(livre: LivreIn, db: Db):
    cur = db.execute(
        "INSERT INTO livre (titre, auteur, annee) VALUES (?, ?, ?)",
        (livre.titre, livre.auteur, livre.annee))
    db.commit()
    return Livre(id=cur.lastrowid, **livre.model_dump())

#3- Lire et chercher
@app.get("/livres", response_model=list[Livre])
def lister(db: Db,
           q: str | None = None,
           skip: int = Query(0, ge=0),
           limit: int = Query(20, ge=1, le=100)):
    sql, params = "SELECT * FROM livre", []
    if q:
        sql += " WHERE titre LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY titre LIMIT ? OFFSET ?"
    params += [limit, skip]
    return [dict(l) for l in db.execute(sql, params).fetchall()]

@app.get("/livres/{livre_id}", response_model=Livre)
def lire(livre_id: int, db: Db):
    return lire_ou_404(db, livre_id)
#4- Modifier
@app.put("/livres/{livre_id}", response_model=Livre)
def modifier(livre_id: int, livre: LivreIn, db: Db):
    lire_ou_404(db, livre_id)
    db.execute(
        "UPDATE livre SET titre = ?, auteur = ?, annee = ? WHERE id = ?",
        (livre.titre, livre.auteur, livre.annee, livre_id))
    db.commit()
    return Livre(id=livre_id, **livre.model_dump())
#5- Supprimer
@app.delete("/livres/{livre_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer(livre_id: int, db: Db):
    lire_ou_404(db, livre_id)
    db.execute("DELETE FROM livre WHERE id = ?", (livre_id,))
    db.commit()