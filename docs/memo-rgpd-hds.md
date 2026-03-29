# Declio — Memo RGPD & Hebergement des Donnees de Sante

**Obligations reglementaires et mesures a mettre en place**

## Perimetre de ce document

Ce memo couvre uniquement les obligations applicables a Declio dans son perimetre PoC :
secretaire vocale IA, gestion d'agenda, rappels de RDV, notifications SMS.
La facturation (SESAM-Vitale, NGAP) est volontairement hors scope.

---

## 1. RGPD renforce : donnees de sante

### 1.1 Pourquoi le RGPD est renforce ici

Le RGPD standard s'applique a toutes les donnees personnelles. Mais les donnees de sante sont classees dans une categorie speciale (article 9 du RGPD) qui impose des obligations supplementaires strictes.

Dans le cadre de Declio, les donnees traitees sont :

- Nom et prenom du patient
- Numero de telephone
- Motif d'appel (peut impliquer une pathologie)
- Horaire et historique de rendez-vous (revele un suivi medical)
- Transcription vocale de l'appel

> **Attention**
> Meme si Declio ne stocke pas de diagnostic medical, le simple fait de savoir
> qu'une personne consulte un kinesitherapeute est considere comme une donnee de sante
> par la CNIL et les tribunaux europeens. Le regime renforce s'applique donc.

### 1.2 Les 7 mesures obligatoires

#### Mesure 1 : Base legale du traitement

Declio ne peut traiter des donnees de sante qu'avec une base legale valide. La base applicable ici est le consentement explicite du patient ou la necessite pour l'execution d'un contrat de soins.

En pratique : un message d'information doit etre joue au debut de chaque appel traite par Declio :

> **Message a diffuser obligatoirement**
> "Cet appel est pris en charge par un assistant virtuel au nom du cabinet [Nom].
> Vos donnees sont traitees conformement au RGPD. Pour en savoir plus,
> contactez directement le cabinet."

#### Mesure 2 : Durees de conservation

Les donnees ne peuvent pas etre conservees indefiniment. Les durees maximales recommandees par la CNIL pour ce type de traitement :

| Type de donnee | Duree de conservation |
|---|---|
| Transcription vocale | Supprimee immediatement apres generation du resume SMS. Non stockee. |
| Resume SMS (meta-donnee) | 3 mois maximum, puis suppression automatique. |
| Coordonnees patient (nom, tel) | Duree de la relation avec le cabinet + 1 an. |
| Historique RDV | 2 ans maximum apres le dernier RDV. |
| Logs systeme | 3 mois, anonymises. |

#### Mesure 3 : Droits des personnes

Chaque patient a des droits sur ses donnees. Declio doit etre en mesure de les honorer dans un delai de 30 jours :

- **Droit d'acces** : le patient peut demander quelles donnees sont stockees le concernant
- **Droit de rectification** : correction des donnees erronees
- **Droit a l'effacement** : suppression de toutes ses donnees sur demande
- **Droit a la portabilite** : export des donnees dans un format lisible
- **Droit d'opposition** : refus du traitement automatise

En pratique : une adresse email de contact (ex : privacy@declio.fr) doit etre communiquee dans les CGU et dans les CGV signees avec chaque cabinet.

#### Mesure 4 : DPA (Data Processing Agreement)

Declio est un sous-traitant au sens du RGPD : il traite des donnees pour le compte du kinesitherapeute (responsable de traitement). Un contrat de sous-traitance doit etre signe avant tout deploiement.

Ce contrat doit obligatoirement mentionner :

- La nature et la finalite du traitement
- Les categories de donnees traitees
- Les mesures de securite mises en place
- Les sous-traitants ulterieurs eventuels (ex : fournisseur cloud, Twilio)
- Les modalites de suppression des donnees en fin de contrat

> **Action requise**
> Faire rediger ce DPA par un avocat specialise en droit de la sante numerique.
> Budget estime : 500 a 1 000 euros. A faire une fois, reutilisable pour tous les clients.
> Ressource recommandee : CNIL - modele de clause contractuelle pour sous-traitants.

#### Mesure 5 : Registre des traitements

Tout responsable de traitement ou sous-traitant doit tenir un registre documentant tous ses traitements de donnees. C'est un document interne, pas a publier, mais exigible par la CNIL en cas de controle.

Pour Declio, le registre doit couvrir au minimum :

- Traitement 1 : Transcription et resume d'appels entrants
- Traitement 2 : Gestion des rendez-vous patients
- Traitement 3 : Envoi de rappels SMS aux patients
- Traitement 4 : Logs d'utilisation du service

Format : un tableau simple (Excel ou Notion) mis a jour a chaque nouveau traitement. La CNIL met a disposition un modele gratuit sur cnil.fr.

#### Mesure 6 : Analyse d'impact (AIPD)

Une Analyse d'Impact sur la Protection des Donnees est obligatoire pour les traitements a risque eleve. Le traitement de donnees de sante par un systeme automatise (IA vocale) rentre dans ce cadre.

L'AIPD doit documenter :

- La description du traitement et ses finalites
- L'evaluation des risques pour les personnes concernees
- Les mesures techniques et organisationnelles pour attenuer ces risques

La CNIL propose un outil gratuit : PIA (Privacy Impact Assessment), disponible sur cnil.fr/fr/outil-pia-telechargez-et-installez-le-logiciel-de-la-cnil.

#### Mesure 7 : Violation de donnees

En cas de fuite ou de violation de donnees de sante, Declio doit notifier la CNIL dans les 72 heures et, si le risque est eleve, informer les personnes concernees.

A mettre en place : une procedure interne de gestion des incidents avec un responsable designe et un modele de notification CNIL pret a l'emploi.

---

## 2. Hebergement des Donnees de Sante (HDS)

### 2.1 Qu'est-ce que la certification HDS

La certification HDS (Hebergement de Donnees de Sante) est obligatoire en France pour tout acteur qui heberge, maintient ou exploite des donnees de sante a caractere personnel pour le compte de professionnels de sante ou d'etablissements de sante.

Elle est definie par l'article L.1111-8 du Code de la Sante Publique et le decret du 12 septembre 2018. Elle est delivree par des organismes accredites (Bureau Veritas, BSI, Apave...) sur la base de la norme ISO 27001 enrichie d'exigences specifiques sante.

> **Ce que ca signifie pour Declio**
> Declio n'a pas besoin d'obtenir lui-meme la certification HDS.
> Il doit simplement heberger ses donnees de sante chez un prestataire certifie HDS.
> C'est une ligne de configuration dans ton infrastructure, pas un chantier de certification.

### 2.2 Quelle donnee necessite un hebergement HDS

Pas toutes les donnees de Declio n'ont besoin d'etre hebergees en HDS. Voici la separation claire :

| Type de donnee | Hebergement HDS requis |
|---|---|
| Transcriptions d'appels | **OUI** - contient potentiellement un motif medical |
| Noms et telephones patients | **OUI** - lie a un suivi de sante |
| Historique des RDV | **OUI** - revele un suivi medical |
| Resumes SMS envoyes | **OUI** - si le contenu mentionne un contexte medical |
| Configuration du cabinet (nom, adresse, tarifs) | NON - donnees purement administratives |
| Logs techniques anonymises | NON - pas de donnees personnelles |
| Donnees de facturation Declio (abonnement) | NON - donnees commerciales |

### 2.3 Les operateurs francais certifies HDS recommandes

#### OVHcloud (recommande pour demarrer)

- Certification HDS obtenue depuis 2018, renouvelee annuellement
- Datacenter 100% sur le territoire francais (Roubaix, Strasbourg, Gravelines)
- Offre HDS disponible sur leurs gammes VPS et instances cloud (Public Cloud)
- Prix : a partir de 50 a 80 euros/mois pour une instance avec garanties HDS
- Documentation disponible sur ovhcloud.com/fr/enterprise/certification-conformite/hds
- **Avantage** : support en francais, bonne documentation, prix competitif pour early stage

#### Scaleway (alternative moderne)

- Filiale du groupe Iliad (Free), infrastructure 100% francaise
- Certification HDS sur leurs offres Instances et Managed Database
- Interface developer-friendly, API complete
- Prix comparables a OVH, parfois plus avantageux sur les petites instances
- **Avantage** : stack moderne, bonne experience developpeur

#### Microsoft Azure France Central (si besoin d'ecosysteme enterprise)

- Datacenter en region France Central (Paris) et France South (Marseille)
- Certification HDS sur la majorite des services (IaaS, PaaS)
- Plus cher qu'OVH ou Scaleway mais offre plus de services manages
- Pertinent si tu envisages une integration avec des outils Microsoft (Teams, etc.)
- **Avantage** : ecosysteme tres riche, SLA enterprise

> **Recommandation pour le PoC**
> Commencer avec OVHcloud ou Scaleway.
> Les deux sont certifies HDS, heberges en France, et adaptes a un projet early stage.
> Prevoir 50 a 100 euros/mois pour l'infrastructure HDS du PoC.
> Monter vers Azure uniquement si tu signes des clients enterprise qui l'exigent contractuellement.

### 2.4 Comment configurer un hebergement HDS en pratique

1. **Creer un compte OVHcloud ou Scaleway et selectionner une offre estampillee HDS dans leur catalogue**
   - Sur OVH : aller dans Public Cloud > Instances > filtrer par 'HDS'
   - Sur Scaleway : aller dans Compute > Instances > activer l'option 'Compliance HDS'

2. **Signer le contrat specifique HDS propose par l'hebergeur**
   - Ce contrat est distinct des CGV standard
   - Il definit les responsabilites de l'hebergeur sur la securite des donnees de sante

3. **Isoler les donnees de sante sur cette infrastructure**
   - Ne pas mixer donnees de sante et donnees non-sensibles sur le meme serveur
   - Creer une base de donnees dediee pour les transcriptions et historiques RDV

4. **Configurer le chiffrement**
   - Chiffrement des donnees au repos (AES-256 minimum)
   - Chiffrement des donnees en transit (TLS 1.2 minimum)
   - Les deux sont generalement inclus dans les offres HDS des grands operateurs

5. **Documenter l'hebergeur dans ton DPA**
   - Mentionner OVH ou Scaleway comme sous-traitant ulterieur dans le contrat signe avec chaque cabinet
   - Fournir la reference de certification HDS de l'hebergeur si demande

---

## 3. Checklist de mise en conformite

### Avant le premier cabinet pilote (PoC)

| Action | Detail | Priorite |
|---|---|---|
| Choisir un hebergeur HDS | OVHcloud ou Scaleway, offre HDS | Urgent |
| Signer le contrat HDS hebergeur | Distinct des CGV standard | Urgent |
| Rediger le DPA cabinet | Avec un avocat, 500-1000 euros | Urgent |
| Message vocal RGPD | Joue au debut de chaque appel | Urgent |
| Configurer suppression auto transcriptions | Suppression apres generation resume | Urgent |
| Creer registre des traitements | Modele CNIL gratuit | Important |

### Avant commercialisation (v1)

| Action | Detail | Priorite |
|---|---|---|
| Realiser l'AIPD | Outil PIA de la CNIL | Obligatoire |
| Rediger politique de confidentialite | Publiee sur le site Declio | Obligatoire |
| Rediger CGV incluant clauses RGPD | Avec avocat | Obligatoire |
| Creer adresse privacy@declio.fr | Pour les demandes de droits | Important |
| Procedure de gestion des incidents | Notification CNIL sous 72h | Important |
| Audit securite infrastructure | Pentest basique ou auto-evaluation | Recommande |

---

## 4. Ressources utiles

| Ressource | URL |
|---|---|
| CNIL - Guide sous-traitants | cnil.fr/fr/les-sous-traitants-une-relation-encadree |
| CNIL - Outil AIPD (PIA) | cnil.fr/fr/outil-pia-telechargez-et-installez-le-logiciel-de-la-cnil |
| ANS - Certification HDS | esante.gouv.fr/produits-services/hds |
| OVHcloud HDS | ovhcloud.com/fr/enterprise/certification-conformite/hds |
| Scaleway HDS | scaleway.com/fr/hebergement-donnees-de-sante-hds |
| CNDA - Agrements SESAM-Vitale | cnda.ameli.fr (hors scope pour Declio) |

---

*Declio | Ce document ne constitue pas un avis juridique. Consulter un avocat specialise avant tout deploiement.*
