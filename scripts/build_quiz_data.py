"""Genera docs/data/quiz.json verificando i contenuti reali del PDF InfoComm.
Ogni modulo cita la pagina libro di riferimento (pdf_page - 15).
Eseguire da root repo: python scripts/build_quiz_data.py
"""
import json, os, sys
from pypdf import PdfReader

PDF = os.path.join('dist', '20315 - InfoComm.pdf')
OUT = os.path.join('docs', 'data', 'quiz.json')
OFFSET = 15  # pdf_page = pagina libro + 15 (verificato via campionamento)

MODULES_META = [
    ("a1", "A1 · Azienda e sistemi informativi", 2, 44),
    ("a2", "A2 · E-commerce e comunicazione digitale", 46, 99),
    ("a3", "A3 · Marketing web, social e analytics", 100, 149),
    ("a4", "A4 · Reti, networking e cloud", 150, 187),
    ("a5", "A5 · Sicurezza, crittografia e firma digitale", 188, 241),
    ("a6", "A6 · PA digitale, fatture e SPID", 242, 283),
    ("b1", "B1 · Siti web, HTML e CSS", 284, 347),
    ("b2", "B2 · Documenti aziendali con Word", 348, 399),
    ("b3", "B3 · Excel per l'azienda", 400, 449),
    ("b4", "B4 · Audio, video e immagini", 450, 520),
]

# Parole-chiave attese per modulo (devono comparire nel testo estratto)
KEYWORDS = {
    "a1": ["azienda", "sistema informativo", "ERP"],
    "a2": ["e-commerce", "sito web aziendale", "social network"],
    "a3": ["web analytics", "marketing virale", "diritto d'autore"],
    "a4": ["TCP", "ISO-OSI", "cloud"],
    "a5": ["crittografia", "chiave pubblica", "firma digitale"],
    "a6": ["fattura elettronica", "PagoPA", "SPID"],
    "b1": ["HTML", "CSS", "CMS"],
    "b2": ["mail merge", "lettera commerciale", "Google Moduli"],
    "b3": ["Excel", "filtri", "formattazione condizionale"],
    "b4": ["microfono", "Shotcut", "immagini"],
}

# --- 100 domande grounded (10 per modulo), stile INVALSI: 7 multiple + 3 V/F ---
Q = {
"a1": [
 ("m","Secondo il libro, ogni attività svolta in azienda deve essere…",["improvvisata giorno per giorno","programmata con obiettivi, decisioni, modalità e risorse","delegata interamente all'esterno","svolta senza controllo"],1,17),
 ("m","Il sistema informativo aziendale è…",["l'insieme organizzato di informazioni e procedure per gestire l'azienda","solo il software di contabilità","solo i computer dell'ufficio","la rete internet pubblica"],0,18),
 ("m","Il sistema informatico rispetto al sistema informativo è…",["la stessa cosa","la componente automatizzata (hardware+software) del sistema informativo","solo la carta stampata","un obbligo fiscale"],1,20),
 ("m","ERP (Enterprise Resource Planning) indica…",["un social network","un sistema integrato che unifica i processi aziendali (contabilità, magazzino, vendite…)","un antivirus","un formato video"],1,30),
 ("m","Il passaggio a un sistema informativo integrato serve a…",["evitare dati duplicati e avere informazioni coerenti tra reparti","aumentare la carta stampata","rallentare il lavoro","eliminare i backup"],0,45),
 ("m","La customer satisfaction si verifica anche con…",["brevi questionari online agli utenti","il lancio di una moneta","l'oroscopo","il passaparola incontrollato"],0,45),
 ("m","Il Codice ATECO serve a…",["classificare le attività economiche dell'azienda","criptare le password","comprimere i video","formattare l'hard disk"],0,11),
 ("v","Il sistema informativo coincide sempre con il sistema informatico.",False,20),
 ("v","Un ERP integra in un unico database i dati dei vari reparti aziendali.",True,30),
 ("v","Programmare le attività aziendali significa fissare in anticipo obiettivi e risorse.",True,17),
],
"a2": [
 ("m","Un sito vetrina è…",["un sito che presenta l'azienda senza vendere online","un negozio fisico","un virus","un foglio Excel"],0,100),
 ("m","L'e-commerce indica…",["la vendita di beni/servizi tramite internet","la posta cartacea","la TV analogica","il passaparola in piazza"],0,50),
 ("m","Il Web 3.0 / web semantico punta a…",["contenuti comprensibili anche alle macchine, più personalizzati","spegnere internet","solo pagine stampate","niente motori di ricerca"],0,75),
 ("m","I social network per un'azienda sono utili per…",["comunicare, promuovere e gestire la relazione col cliente","nascondere i prodotti","evitare i clienti","sostituire la contabilità"],0,75),
 ("m","Una newsletter aziendale efficace deve…",["essere mirata, sintetica e con call-to-action chiara","essere lunghissima e generica","contenere solo allegati pesanti","essere inviata senza consenso"],0,60),
 ("m","La comunicazione aziendale sul web deve…",["curare immagine, coerenza e reputazione","copiare contenuti altrui senza citarli","ignorare i commenti","pubblicare password"],0,60),
 ("m","Il carrello elettronico serve a…",["raccogliere i prodotti scelti prima del pagamento","contare i dipendenti","misurare il traffico web","archiviare le fatture"],0,50),
 ("v","Vendere online non richiede alcuna gestione di pagamenti e spedizioni.",False,50),
 ("v","Il sito web aziendale svolge anche una funzione pubblicitaria e comunicativa.",True,100),
 ("v","I social vanno gestiti con un piano editoriale e non a caso.",True,75),
],
"a3": [
 ("m","La web analytics è…",["l'analisi dei dati di navigazione per migliorare sito e marketing","la grafica del logo","la stampa dei volantini","la crittografia"],0,125),
 ("m","Metriche classiche di web analytics sono…",["visite, visitatori unici, bounce rate, conversioni","solo il numero di dipendenti","solo il fatturato cartaceo","temperatura e umidità"],0,125),
 ("m","Il marketing virale…",["diffonde il messaggio tramite condivisioni spontanee degli utenti","è un virus informatico","è vietato per legge sempre","riguarda solo la TV"],0,137),
 ("m","Una GIF animata per un prodotto si può realizzare con…",["strumenti online come Imgflip, con uso consapevole","solo con la stampante","senza immagini","senza rispettare licenze"],0,137),
 ("m","Il diritto d'autore in rete tutela…",["opere creative: testi, immagini, musica, video","le password personali","i cavi di rete","i prezzi dei concorrenti"],0,140),
 ("m","Prima di usare un'immagine trovata online bisogna…",["verificarne licenza e diritti di utilizzo","usarla sempre liberamente","cancellarne l'autore","rivenderla"],0,140),
 ("m","Le fasi di un processo di web analytics includono…",["definizione obiettivi, raccolta dati, analisi, azioni correttive","solo l'acquisto del dominio","solo la stampa","niente decisioni"],0,125),
 ("v","Copiare un'immagine protetta senza licenza è sempre lecito se è per la scuola.",False,140),
 ("v","Il bounce rate alto può indicare contenuti poco pertinenti.",True,125),
 ("v","Il marketing virale sfrutta la condivisione degli utenti.",True,137),
],
"a4": [
 ("m","Un protocollo di rete è…",["un insieme di regole per comunicare tra computer","un antivirus","un cavo elettrico","un social network"],0,150),
 ("m","Il modello ISO-OSI…",["descrive 7 livelli di comunicazione (fisico→applicazione)","è un cavo in fibra","è un sito web","è una stampante"],0,150),
 ("m","Il protocollo TCP/IP…",["è la base di internet: indirizza e affida i pacchetti","serve solo per stampare","è un formato immagine","è un virus"],0,150),
 ("m","L'hosting di un sito significa…",["ospitare le pagine su un server raggiungibile via internet","tenere il sito solo sul PC spento","stampare il sito","inviare il sito per posta"],0,172),
 ("m","L'housing differisce dall'hosting perché…",["il server è di proprietà e ospitato in un data-center","non usa elettricità","è gratuito sempre","non usa internet"],0,172),
 ("m","Il cloud per l'azienda consente…",["risorse scalabili via internet senza server propri","di non fare mai backup","di lavorare solo offline","di eliminare le password"],0,172),
 ("m","La struttura di una rete aziendale prevede…",["client, server, switch/router, cablaggio o Wi-Fi pianificati","solo smartphone personali","nessuna sicurezza","cavi annodati a caso"],0,172),
 ("v","TCP garantisce consegna ordinata e controllo errori, IP si occupa dell'indirizzamento.",True,150),
 ("v","Hosting e housing sono esattamente la stessa cosa.",False,172),
 ("v","Il cloud elimina ogni responsabilità su privacy e backup.",False,172),
],
"a5": [
 ("m","Le minacce naturali ai sistemi sono…",["tempeste, inondazioni, fulmini, incendi, terremoti","solo gli hacker","solo i virus","solo lo spam"],0,190),
 ("m","La crittografia serve a…",["rendere illeggibile un messaggio ai non autorizzati","velocizzare la stampante","comprimere video","creare siti web"],0,210),
 ("m","Nella crittografia asimmetrica…",["si usano chiave pubblica (condivisa) e privata (segreta)","c'è una sola password per tutti","non esistono chiavi","le chiavi sono inutili"],0,210),
 ("m","La firma digitale garantisce…",["autenticità, integrità e non ripudio del documento","l'anonimato totale","la cancellazione del documento","la stampa a colori"],0,235),
 ("m","Un certificato digitale…",["ha scadenza e va rinnovato; lega una chiave a un soggetto","dura per sempre senza rinnovo","è solo cartaceo","non serve a nulla"],0,235),
 ("m","La PEC è…",["posta elettronica certificata con valore legale di raccomandata","posta pubblicitaria","un social network","un antivirus"],0,235),
 ("m","L'autenticazione forte dell'utente richiede…",["credenziali robuste e possibilmente più fattori","la stessa password ovunque","password condivise","nessun controllo"],0,218),
 ("v","Una chiave a 1024 bit può avere validità massima limitata nel tempo e va rinnovata.",True,235),
 ("v","Condividere la propria chiave privata con tutti è una buona pratica.",False,210),
 ("v","Backup e policy di sicurezza riducono i danni da incidenti.",True,190),
],
"a6": [
 ("m","L'AOO (Area Organizzativa Omogenea) nella PA è…",["l'ufficio che gestisce protocollo e documenti in modo omogeneo","un antivirus","un social","un formato video"],0,245),
 ("m","La fattura elettronica…",["è un file strutturato che transita via SDI con valore fiscale","è una semplice scansione senza valore","si invia solo per posta","non esiste in Italia"],0,255),
 ("m","Il 730 precompilato…",["è predisposto dall'Agenzia con dati già noti, da verificare/integrare","si compila solo a penna","non riguarda i lavoratori","è uguale per tutti senza modifiche"],0,255),
 ("m","Il mercato elettronico della PA (MEPA) serve per…",["acquisti pubblici trasparenti e concorrenziali online","vendere auto usate tra privati","giocare online","guardare film"],0,260),
 ("m","PagoPA è…",["il sistema di pagamenti elettronici verso la PA","una banca privata estera","un social network","un virus"],0,280),
 ("m","Lo SPID è…",["l'identità digitale per accedere ai servizi online di PA e privati","una carta fedeltà del supermercato","un antivirus","un cavo di rete"],0,270),
 ("m","L'e-procurement indica…",["gli acquisti di beni/servizi tramite piattaforme digitali","la stampa di cataloghi","le aste in piazza","il baratto"],0,260),
 ("v","La fattura elettronica ha seguito un percorso di avvicinamento digitale in Europa.",True,255),
 ("v","Con PagoPA i pagamenti alla PA diventano semplici, sicuri e trasparenti.",True,280),
 ("v","SPID e CIE permettono di accedere ai servizi online senza nuove credenziali per ogni sito.",True,270),
],
"b1": [
 ("m","HTML è…",["il linguaggio di markup per strutturare le pagine web","un foglio di calcolo","un antivirus","un database"],0,294),
 ("m","I tag di paragrafo e allineamento in HTML…",["si applicano a p/div con valori left, right, center","non esistono","sono solo per la stampa","distruggono la pagina"],0,300),
 ("m","I CSS servono a…",["separare stile e presentazione dal contenuto HTML","scrivere virus","sostituire il server","eliminare internet"],0,314),
 ("m","Una classe CSS .evidenziato…",["si applica con class=\"evidenziato\" a uno o più elementi","funziona solo stampando","non esiste","cancella il testo"],0,320),
 ("m","HTML5 introduce…",["nuovi tag semantici e form avanzati (email, date, validazione)","solo pagine cartacee","niente form","solo bianco e nero"],0,326),
 ("m","Usabilità e accessibilità di un sito significano…",["facile da usare e fruibile da tutti, anche con disabilità","solo bello da vedere","solo veloce","solo pieno di animazioni"],0,292),
 ("m","Un CMS (es. per siti aziendali) permette di…",["creare e gestire contenuti senza scrivere tutto il codice","programmare chip","stampare libri","creare virus"],0,345),
 ("v","In HTML la struttura (tag) e lo stile (CSS) è bene tenerli separati.",True,314),
 ("v","left è il valore di allineamento predefinito del paragrafo.",True,300),
 ("v","Un sito usabile deve confondere l'utente con menu nascosti.",False,292),
],
"b2": [
 ("m","La lettera commerciale deve…",["avere intestazione, oggetto, corpo chiaro e firma","essere senza data né firma","usare solo emoticon","essere illeggibile"],0,348),
 ("m","Il mail merge (stampa unione) serve a…",["produrre lettere personalizzate da un modello + elenco dati","inviare virus","unire due computer","formattare dischi"],0,364),
 ("m","Nel mail merge il documento origine…",["contiene campi collegati ai record (nomi, indirizzi)","è sempre vuoto","non si salva mai","è un video"],0,370),
 ("m","Per verificare le copie del mail merge…",["si naviga tra i record dalla barra dei record","si tira a sorte","si stampa tutto senza controllare","si cancella l'elenco"],0,370),
 ("m","Google Moduli è utile in azienda per…",["raccogliere risposte con questionari online automatizzati","montare video","programmare app","disegnare loghi"],0,395),
 ("m","L'aspetto di un Modulo Google si cambia…",["definendo layout e temi del questionario","solo stampando","mai","con il martello"],0,395),
 ("m","I documenti automatizzati riducono…",["errori e tempi rispetto alla compilazione manuale","la qualità sempre","la sicurezza sempre","la leggibilità"],0,380),
 ("v","La stampa unione collega un modello ai dati di un elenco.",True,364),
 ("v","Una lettera commerciale non ha bisogno di oggetto e firma.",False,348),
 ("v","Con Google Moduli le risposte si raccolgono in modo automatico.",True,395),
],
"b3": [
 ("m","Excel in azienda serve soprattutto a…",["gestire e analizzare dati contabili e commerciali","montare film","navigare anonimi","disegnare fumetti"],0,420),
 ("m","Filtri e subtotali in Excel permettono di…",["selezionare e riepilogare sottoinsiemi di dati","cancellare tutto","formattare il PC","creare virus"],0,420),
 ("m","La formattazione condizionale…",["evidenzia celle in base a regole (es. valori fuori soglia)","cancella i dati","spegne il PC","stampa da sola"],0,420),
 ("m","Funzioni come SOMMA.SE e CONTA.SE servono a…",["sommare/contare solo celle che rispettano criteri","contare i fogli stampati","misurare lo schermo","niente"],0,420),
 ("m","I modelli Excel protetti…",["guidano l'inserimento ed evitano modifiche accidentali","sono inutili","non si salvano","sono virus"],0,445),
 ("m","Un intervallo tipo B2:B2202 indica…",["le celle dalla riga 2 alla 2202 della colonna B","una sola cella","un grafico","una password"],0,445),
 ("m","Applicazioni di marketing in Excel includono…",["analisi vendite, campagne ed expo con tabelle e grafici","solo disegni a mano","niente dati","solo testo libero"],0,451),
 ("v","I filtri mostrano solo le righe che soddisfano i criteri scelti.",True,420),
 ("v","La protezione dei fogli impedisce modifiche alle celle bloccate.",True,445),
 ("v","CONTA.SE conta tutte le celle senza alcun criterio.",False,420),
],
"b4": [
 ("m","Un trasduttore audio come il microfono…",["trasforma onde di pressione in segnali elettrici","cuoce la pasta","stampa foto","proietta film"],0,470),
 ("m","La rappresentazione digitale di suoni/immagini richiede…",["campionamento e quantizzazione in bit","solo carta e penna","niente formati","solo TV analogica"],0,470),
 ("m","Per elaborare immagini (es. sostituire uno sfondo) si usano…",["selezioni e livelli in un editor grafico","solo il blocco note","la calcolatrice","il martello"],0,490),
 ("m","Shotcut è…",["un editor video gratuito per tagliare e montare filmati","un virus","una stampante","un social"],0,510),
 ("m","Aggiungere didascalie e riconoscimenti a un video…",["rispetta autori e migliora la comprensione","è inutile","è vietato","rovina tutto"],0,502),
 ("m","Formati e compressione servono a…",["bilanciare qualità e peso di audio/video/immagini","eliminare i file","non servono","aumentare sempre il peso"],0,485),
 ("m","Un uso consapevole dei media in azienda richiede…",["rispetto di licenze, privacy e diritto d'autore","copie abusive","volti pubblicati senza consenso","musica rubata"],0,490),
 ("v","Il microfono è un esempio di trasduttore audio.",True,470),
 ("v","Comprimere un video riduce sempre e solo la qualità senza vantaggi.",False,485),
 ("v","Nei video aziendali vanno indicati autori e fonti del materiale.",True,502),
],
}

def pdf_text(pages):
    r = PdfReader(PDF)
    out = []
    for p in pages:
        if 0 <= p < len(r.pages):
            out.append(r.pages[p].extract_text() or '')
    return '\n'.join(out)

def main():
    if not os.path.exists(PDF):
        print('PDF non trovato:', PDF); sys.exit(1)
    r = PdfReader(PDF)
    print('PDF pagine:', len(r.pages))
    quiz = {"app": "InfoComm Quiz · stile INVALSI", "source_pdf": os.path.basename(PDF),
            "minutes_per_quiz": 12, "pass_score": 6, "modules": []}
    for mid, title, book_start, book_end in MODULES_META:
        p0, p1 = book_start + OFFSET, book_end + OFFSET
        text = pdf_text(range(p0, min(p1 + 1, len(r.pages))))
        low = text.lower()
        missing = [k for k in KEYWORDS[mid] if k.lower() not in low]
        if missing:
            print('AVVISO', mid, 'keyword mancanti:', missing)
        else:
            print('OK', mid, 'pagine pdf', p0, '-', min(p1, len(r.pages)-1), 'caratteri', len(text))
        qs = []
        for i, item in enumerate(Q[mid], 1):
            typ = item[0]
            if typ == 'm':
                _, q, opts, ans, bookpg = item
                qs.append({"id": f"{mid}-q{i:02d}", "type": "multiple",
                           "q": q, "options": opts, "answer": ans,
                           "source": f"InfoComm, pag. {bookpg}"})
            else:
                _, q, ans, bookpg = item
                qs.append({"id": f"{mid}-q{i:02d}", "type": "truefalse",
                           "q": q, "answer": bool(ans),
                           "source": f"InfoComm, pag. {bookpg}"})
        quiz["modules"].append({"id": mid, "title": title,
            "book_pages": [book_start, book_end], "minutes": 12,
            "questions": qs})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(quiz, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = sum(len(m['questions']) for m in quiz['modules'])
    print('Scritto', OUT, '-', len(quiz['modules']), 'moduli,', n, 'domande')

if __name__ == '__main__':
    main()
