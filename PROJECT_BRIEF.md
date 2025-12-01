# Project Brief: AlgaInfo - Agente de Investigación Taxonómica

## 1. El Problema y la Visión

### Objetivo Principal
Crear una herramienta de software de vanguardia para taxónomos y investigadores de algas. El objetivo es unificar y facilitar el acceso a información biológica completa y dispersa.

### El Desafío
La información taxonómica, de distribución, morfológica y genética sobre especies de algas está fragmentada en múltiples bases de datos:

*   **Bases de datos de pago:** AlgaeBase es considerada una de las fuentes más completas, pero su API es de pago, limitando su acceso para proyectos independientes.
*   **Bases de datos públicas:** WoRMS (World Register of Marine Species) y GBIF (Global Biodiversity Information Facility) son increíblemente ricas en datos, pero ofrecen diferentes tipos de información (taxonomía vs. ocurrencias/media) y requieren consultas a través de APIs separadas.
*   **Literatura científica:** Descripciones detalladas, diagnosis y discusiones taxonómicas a menudo solo se encuentran en publicaciones (PDFs, artículos en HTML), como las indexadas por Plazi.

Un investigador necesita actualmente consultar todas estas fuentes manualmente para construir un "perfil 360°" de una única especie, un proceso lento e ineficiente.

### La Visión
La visión de AlgaInfo es ser un **asistente de investigación dinámico**. En lugar de ser solo una base de datos estática, la aplicación actuará como un agente inteligente que:
1.  Provee acceso instantáneo a un vasto conjunto de datos pre-compilados.
2.  Cuando la información no está disponible localmente, es capaz de realizar una investigación "profunda" en tiempo real a través de fuentes online, utilizando un modelo de lenguaje (LLM) para orquestar la búsqueda y sintetizar los resultados.
3.  Aprende y se auto-mejora, guardando los resultados de sus investigaciones para enriquecer la base de datos local (caching).

---

## 2. La Arquitectura Propuesta: Agente con "Fallback"

Se ha decidido una arquitectura de dos pasos para equilibrar la velocidad (para datos conocidos) y la exhaustividad (para datos nuevos).

### Paso 1: Búsqueda Local Primero (Rendimiento Óptimo)
Cuando un usuario busca una especie, la aplicación realiza una consulta de alta velocidad contra una base de datos SQLite local (`algae.db`). Si la especie existe en la base de datos, su perfil detallado se muestra instantáneamente.

### Paso 2: "Fallback" al Agente de Investigación (Máxima Cobertura)
Si la búsqueda local no arroja resultados, la interfaz de usuario no se rinde. En su lugar, ofrece al usuario la opción de iniciar una "investigación profunda en tiempo real".

### Paso 3: El Agente en Acción
Al activar la investigación, se invoca a un **Agente inteligente (hecho con google adk,openai agents o langchain)**. Este agente está específicamente diseñado para esta tarea:
*   **Inicialización:** Se le da un `prompt` o instrucciones claras, como: *"Eres un asistente experto en ficología. Investiga a fondo la especie '{nombre_especie}' utilizando las herramientas a tu disposición. Sintetiza un informe completo que incluya taxonomía, estatus, distribución, atributos y cualquier descripción morfológica relevante que encuentres."*
*   **Herramientas (Tools):** El Asistente tiene acceso a un conjunto de funciones de Python que le permiten interactuar con el mundo exterior. El Asistente decidirá autónomamente cuál de estas herramientas usar para cumplir con su objetivo.
    *   `search_local_db(species_name)`
    *   `search_worms_by_name(species_name)`
    *   `get_gbif_descriptions(gbif_key)`
    *   `get_gbif_media(gbif_key)`
    *   (futuras) `search_plazi_literature(species_name)`
*   **Ejecución:** El Asistente ejecutará las herramientas necesarias (posiblemente varias veces) hasta que considere que ha recopilado suficiente información para responder a la solicitud inicial.

### Paso 4: Caching y Auto-Mejora
Una vez que el Agente genera el informe final, los datos brutos recopilados se analizan y se guardan en las tablas correspondientes de la base de datos local `algae.db`. Esto significa que la próxima vez que alguien busque la misma especie, el resultado será instantáneo. La base de datos crece y se vuelve más completa con el uso real de la aplicación.

---

## 3. Estado Actual del Proyecto

El proyecto ha sido reorganizado para adoptar esta nueva arquitectura.

### Estructura del Repositorio
```
.
├── algae.db              # Base de datos SQLite con datos consolidados.
├── algain/                 # Paquete principal de la aplicación.
│   ├── __init__.py
│   ├── agent/              # Lógica del agente.
│   │   ├── __init__.py
│   │   ├── agent.py        # Orquestador del Asistente de OpenAI.
│   │   └── tools/          # Herramientas que el agente puede usar.
│   │       ├── __init__.py
│   │       ├── worms_api.py
│   │       └── gbif_api.py
│   └── db/                 # Lógica de interacción con la BD local.
│       ├── __init__.py
│       └── database.py
├── archive/                # Scripts y datos de la fase inicial de recolección.
├── config.py               # Para configuración y claves de API.
├── main.py                 # Punto de entrada de la aplicación.
└── requirements.txt        # Dependencias de Python.
```

### La Base de Datos (`algae.db`)
Contiene los resultados de la fase de consolidación de datos offline.
*   **Tabla `taxonomy`:**
    *   **Contenido:** Aprox. 11,226 registros de especies.
    *   **Esquema:** `aphia_id` (PK), `scientific_name`, `authority`, `rank`, `status`, `kingdom`, `phylum`, `class`, `order`, `family`, `genus`, `source`.
    *   **Fuentes:** WoRMS y Diatombase (extraídos vía scripts iniciales).
*   **Tabla `distributions`:**
    *   **Contenido:** Aprox. 3.4 millones de registros de ocurrencias.
    *   **Esquema:** `distribution_id` (PK), `aphia_id` (FK a `taxonomy`), `gbif_id`, `decimal_latitude`, `decimal_longitude`, `event_date`, `country_code`.
    *   **Fuente:** GBIF (gbif_occurrences.csv).

### Herramientas del Agente (Desarrolladas)
*   **`search_species_by_name(species_name)`**
    *   **Ubicación:** `algain/agent/tools/worms_api.py`.
    *   **Funcionalidad:** Implementada y probada. Toma un nombre de especie, consulta la API de WoRMS y devuelve un diccionario con la información taxonómica clave. Es la primera herramienta funcional del agente.

---

## 4. Próximos Pasos

El plan de acción inmediato se centra en construir y orquestar el agente.

1.  **Instalar Dependencias:** `pip install openai pandas requests`.
2.  **Configurar Claves de API:** Poblar `config.py` con la clave de API de OpenAI y asegurarse de que se carga de forma segura (p. ej., desde variables de entorno).
3.  **Desarrollar Herramientas Restantes:**
    *   `get_species_from_local_db()` en `algain/db/database.py`.
    *   Funciones en `algain/agent/tools/gbif_api.py` para obtener descripciones textuales e imágenes. Se necesitará un mapeo previo de AphiaID a GBIF Key.
4.  **Implementar el Orquestador del Agente (`agent.py`):**
    *   Escribir el código que crea o carga un agent.
    *   Definir las herramientas (nuestras funciones de Python) en el formato que la API de Asistentes espera (JSON Schema).
    *   Crear un "Thread" para la conversación.
    *   Añadir el mensaje del usuario y ejecutar el Asistente.
    *   Gestionar el bucle de ejecución de herramientas cuando el Asistente lo solicite.
5.  **Crear el Flujo Principal (`main.py`):**
    *   Implementar la lógica principal: recibir un nombre de especie, llamar a `get_species_from_local_db()`, y si no se encuentra, invocar al orquestador del agente.
```