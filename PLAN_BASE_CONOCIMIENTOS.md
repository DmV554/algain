# Plan Estratégico: Base de Conocimientos Robusta para Sistema RAG de Identificación de Algas

## 📊 Estado Actual del Proyecto

### Datos Recolectados
- **DiatomBase**: ~2,106 especies de diatomeas
- **WORMS**: ~9,122 especies de algas marinas
- **Total especies únicas**: ~11,000 especies
- **GBIF**: ~1.6M registros de ocurrencia (coordenadas geográficas, fechas)

### Infraestructura Existente
✅ Scripts funcionales para esqueletos taxonómicos (WORMS, DiatomBase)
✅ Script GBIF con caché y reanudación
✅ Script PubMed básico (con problemas de recuperación)

---

## 🎯 Objetivos de la Base de Conocimientos

Para un sistema RAG robusto que ayude a taxónomos a identificar algas, necesitamos:

### 1. **Información Taxonómica Completa** ✅ (Ya tenemos)
- Nombre científico y autoridad
- Clasificación completa (Reino → Especie)
- Sinónimos y nombres aceptados
- AphiaID como identificador único

### 2. **Información Geográfica y Ecológica** ✅ (Ya tenemos)
- Distribución geográfica (coordenadas de GBIF)
- Hábitats (marino, agua dulce, salobre, terrestre)
- Rangos de temperatura, salinidad si disponibles

### 3. **Información Morfológica** ⚠️ (CRÍTICA - Falta)
- Características morfológicas distintivas
- Dimensiones (longitud, ancho, forma)
- Estructuras celulares específicas
- Características de identificación visual

### 4. **Literatura Científica** ⚠️ (En progreso - necesita mejora)
- Papers de descripción original
- Revisiones taxonómicas
- Claves de identificación
- Estudios morfológicos y ecológicos

### 5. **Imágenes y Datos Visuales** ❌ (Pendiente)
- Microscopía óptica
- Microscopía electrónica (SEM/TEM)
- Dibujos técnicos
- Fotografías en hábitat natural

---

## 🔍 Análisis del Problema con PubMed

### Problemas Identificados
1. **Búsquedas demasiado específicas**: Las consultas con múltiples keywords reducen mucho los resultados
2. **Limitación de PMC Open Access**: Solo busca en artículos de acceso abierto (~3-5M artículos vs 36M en PubMed total)
3. **Falta de fuentes alternativas**: Muchos papers taxonómicos no están en PMC
4. **Sin priorización**: No distingue entre papers de descripción original vs menciones tangenciales

### Tasas de Éxito Esperadas
- **PMC Open Access**: 5-10% de especies tendrán literatura relevante
- **PubMed Completo**: 15-25% tendrán abstracts relevantes
- **Bases especializadas**: 40-60% tendrán información estructurada

---

## 🚀 Estrategia Propuesta: Arquitectura Multi-Fuente

### Nivel 1: Fuentes Estructuradas (PRIORITARIO)
Estas proveen información confiable, estructurada y específica para algas:

#### A. **AlgaeBase API/Scraping** 🌟 CRÍTICO
- **Qué ofrece**: 
  - Descripciones morfológicas detalladas
  - Información ecológica
  - Sinónimos y taxonomía actualizada
  - Referencias bibliográficas primarias
  - Enlaces a imágenes
- **Cobertura**: >150,000 especies de algas (casi todas las tuyas)
- **Método**: Web scraping estructurado (ya tienes AphiaIDs que enlazan)
- **Formato**: HTML parsing → JSON estructurado
- **Prioridad**: ⭐⭐⭐⭐⭐

#### B. **DiatomBase Extended Data**
- **Qué ofrece**:
  - Información morfológica específica de diatomeas
  - Medidas detalladas
  - Hábitat y ecología
- **Cobertura**: Tus 2,106 especies de diatomeas
- **Método**: API REST disponible
- **Prioridad**: ⭐⭐⭐⭐⭐

#### C. **WORMS Extended Attributes**
- **Qué ofrece**:
  - Atributos adicionales vía WoRMS API
  - Vernacular names
  - Referencias bibliográficas
- **Método**: API REST (ya usas parte de esto)
- **Prioridad**: ⭐⭐⭐⭐

### Nivel 2: Literatura Científica (MEJORADO)

#### A. **PubMed/PMC Optimizado** 🔧
**Estrategia de búsqueda en cascada**:

1. **Búsqueda Tier 1 - Descripción Original** (más específica):
   ```
   "Nombre científico"[Title] AND (description OR taxonomy OR new species OR morphology)
   ```

2. **Búsqueda Tier 2 - Literatura Taxonómica**:
   ```
   "Nombre científico"[Title/Abstract] AND (taxonomy OR morphology OR identification)
   ```

3. **Búsqueda Tier 3 - General**:
   ```
   "Nombre científico"[Title/Abstract]
   ```

**Mejoras técnicas**:
- Usar NCBI E-utilities con `retmax` ajustado
- Buscar en **PubMed completo** para obtener abstracts (no solo PMC)
- Priorizar papers con fecha cercana al año de descripción
- Descargar PDFs solo de PMC Open Access
- Guardar abstracts de todos los papers relevantes

**Prioridad**: ⭐⭐⭐⭐

#### B. **bioRxiv/medRxiv** (Preprints)
- Papers recientes no publicados aún
- API gratuita disponible
- **Prioridad**: ⭐⭐⭐

#### C. **CrossRef API**
- Metadatos de papers
- DOIs y referencias
- Abstracts cuando disponibles
- **Prioridad**: ⭐⭐⭐

#### D. **Europe PMC**
- Alternativa/complemento a PMC
- Más contenido europeo
- API similar
- **Prioridad**: ⭐⭐⭐

### Nivel 3: Imágenes y Multimedia

#### A. **Wikimedia Commons / Wikipedia**
- Imágenes con licencia abierta
- Descripciones en múltiples idiomas
- API bien documentada
- **Prioridad**: ⭐⭐⭐⭐

#### B. **iNaturalist**
- Observaciones con fotos
- Validadas por comunidad
- API disponible
- **Prioridad**: ⭐⭐⭐

#### C. **Flickr** (con licencias CC)
- Fotos científicas
- API disponible
- **Prioridad**: ⭐⭐

#### D. **Diatom Image Database** (específico)
- Para las diatomeas
- Imágenes de microscopía
- **Prioridad**: ⭐⭐⭐⭐

---

## 📋 Estructura de Datos Propuesta

### Esquema JSON por Especie

```json
{
  "aphia_id": 1361155,
  "taxonomy": {
    "scientific_name": "Chloropicon laureae",
    "authority": "Lopes dos Santos & Eikrem, 2017",
    "kingdom": "Plantae",
    "phylum": "Chlorophyta",
    "class": "",
    "order": "",
    "family": "",
    "genus": "Chloropicon",
    "synonyms": [],
    "common_names": {}
  },
  "morphology": {
    "description": "Descripción completa de AlgaeBase...",
    "size": {
      "length_um_min": 3.0,
      "length_um_max": 5.0,
      "width_um_min": 2.0,
      "width_um_max": 4.0
    },
    "key_features": [
      "Células esféricas a ovoides",
      "Cloroplasto parietal",
      "..."
    ],
    "distinguishing_characteristics": "..."
  },
  "ecology": {
    "habitat": ["marine"],
    "salinity": "marine",
    "temperature_range": "temperate",
    "distribution_summary": "Coastal waters...",
    "ecological_notes": "..."
  },
  "geographic_distribution": {
    "gbif_occurrences_count": 45,
    "countries": ["US", "UK", "NO"],
    "coordinate_ranges": {
      "lat_min": 35.0,
      "lat_max": 60.0,
      "lon_min": -125.0,
      "lon_max": 10.0
    },
    "occurrence_sample": [
      {
        "lat": 37.495306,
        "lon": -122.498744,
        "date": "2022-01-28",
        "country": "US"
      }
    ]
  },
  "literature": {
    "original_description": {
      "citation": "...",
      "doi": "...",
      "year": 2017,
      "pdf_url": "...",
      "abstract": "..."
    },
    "key_references": [
      {
        "pmid": "...",
        "pmcid": "...",
        "title": "...",
        "authors": "...",
        "year": 2018,
        "journal": "...",
        "doi": "...",
        "abstract": "...",
        "pdf_available": true,
        "pdf_path": "...",
        "relevance_score": 0.95
      }
    ],
    "total_papers_found": 12
  },
  "images": {
    "microscopy": [
      {
        "url": "...",
        "type": "SEM",
        "magnification": "5000x",
        "source": "...",
        "license": "CC-BY"
      }
    ],
    "diagrams": [],
    "photos": []
  },
  "data_sources": {
    "algaebase_url": "...",
    "diatombase_url": "...",
    "worms_url": "...",
    "last_updated": "2025-10-22"
  },
  "completeness_score": 0.85
}
```

---

## 🛠️ Implementación por Fases

### **FASE 1: Fundación (Semana 1-2)** 🏗️

#### 1.1 Unificar Esqueletos
- Crear dataset maestro unificado (11K especies)
- Eliminar duplicados completos
- Resolver conflictos taxonómicos
- **Output**: `master_species_list.csv`

#### 1.2 Enriquecer con AlgaeBase
- Script de scraping robusto para AlgaeBase
- Extraer descripciones morfológicas
- Extraer información ecológica
- Guardar HTML cacheado para re-parsing
- **Output**: `algaebase_data/{aphia_id}.json`

#### 1.3 Datos Extendidos WoRMS
- Usar WoRMS API para atributos adicionales
- Obtener sinónimos completos
- Referencias bibliográficas
- **Output**: `worms_extended/{aphia_id}.json`

### **FASE 2: Literatura Mejorada (Semana 2-3)** 📚

#### 2.1 Reescribir Motor de PubMed
- Implementar búsqueda en cascada (3 tiers)
- Buscar en PubMed completo (no solo PMC)
- Guardar abstracts de TODOS los papers
- Descargar PDFs solo de PMC Open Access
- Sistema de scoring de relevancia
- **Output**: `literature_data/{aphia_id}/`

#### 2.2 Integrar Fuentes Adicionales
- Europe PMC
- bioRxiv/medRxiv
- CrossRef para DOIs y metadata
- **Output**: Agregado a `literature_data/`

### **FASE 3: Contenido Visual (Semana 3-4)** 🖼️

#### 3.1 Recolección de Imágenes
- Wikipedia/Wikimedia Commons
- iNaturalist
- Diatom Image Database (para diatomeas)
- Flickr con licencias apropiadas
- **Output**: `images/{aphia_id}/`

#### 3.2 Metadatos de Imágenes
- Tipo (microscopía, foto, diagrama)
- Licencia
- Fuente y créditos
- **Output**: `image_metadata/{aphia_id}.json`

### **FASE 4: Consolidación y Vector DB (Semana 4-5)** 🎯

#### 4.1 Generación de Knowledge Base
- Consolidar todos los datos en JSONs estructurados
- Calcular score de completeness por especie
- Generar estadísticas de cobertura
- **Output**: `knowledge_base/{aphia_id}.json`

#### 4.2 Preparación para RAG
- Generar chunks de texto optimizados
- Crear embeddings (OpenAI/Cohere/local)
- Indexar en vector database (Pinecone/Weaviate/ChromaDB)
- **Output**: Base vectorial lista para RAG

#### 4.3 Validación de Calidad
- Identificar especies con baja completeness
- Priorizar re-colección
- Validación manual de muestra

---

## 📊 Métricas de Éxito

### Cobertura Esperada (11,000 especies)

| Tipo de Información | Cobertura Esperada | Crítico para RAG |
|---------------------|-------------------|------------------|
| Taxonomía básica | 100% | ✅ Sí |
| GBIF distribución | ~90% | ✅ Sí |
| AlgaeBase morfología | 70-85% | ✅✅✅ SÍ |
| Literatura (abstracts) | 40-60% | ✅✅ Sí |
| PDFs completos | 10-20% | ⚠️ Deseable |
| Imágenes | 30-50% | ✅✅ Muy importante |

### Score de Completeness por Especie

```python
completeness_score = (
    0.10 * (taxonomía_completa) +
    0.25 * (morfología_presente) +
    0.20 * (ecología_presente) +
    0.15 * (distribución_geográfica) +
    0.20 * (literatura_presente) +
    0.10 * (imágenes_presentes)
)
```

**Objetivo**: >70% de especies con score >0.6

---

## ⚡ Priorización de Recursos

### Tiempo de Desarrollo
1. **AlgaeBase scraper**: 2-3 días (MÁXIMA PRIORIDAD)
2. **PubMed mejorado**: 2 días
3. **Consolidación de datos**: 2 días
4. **Sistema de imágenes**: 3 días
5. **Vector DB y RAG prep**: 2 días

### APIs Rate Limits a Considerar
- **NCBI E-utilities**: 3 req/sec sin API key, 10 req/sec con key (GRATIS)
- **AlgaeBase**: Sin API oficial, respetar robots.txt, 1 req/2sec recomendado
- **WORMS**: 1 req/sec recomendado
- **GBIF**: Ya tienes datos cacheados ✅
- **WikiMedia**: 200 req/sec (muy generoso)
- **iNaturalist**: 60 req/min

---

## 🎓 Por Qué Este Enfoque

### 1. **AlgaeBase es LA fuente crítica**
- Es la base de datos taxonómica más completa de algas
- Contiene descripciones morfológicas que NO están en papers
- Es curada por expertos
- Ya tienes los AphiaIDs que enlazan perfectamente

### 2. **PubMed solo no es suficiente**
- Solo ~10-20% de tus especies tendrán papers en PMC Open Access
- Los abstracts son más valiosos que PDFs completos para RAG
- Necesitas múltiples fuentes

### 3. **RAG necesita diversidad de contenido**
- Descripciones concisas (AlgaeBase)
- Literatura contextual (PubMed abstracts)
- Datos estructurados (taxonomía, geográficos)
- Contenido visual (para modelos multimodales futuros)

### 4. **Escalabilidad**
- 11K especies × 5 segundos/especie = ~15 horas de procesamiento
- Con paralelización responsable: 6-8 horas
- Caché evita re-trabajo

---

## 🚦 Próximos Pasos Inmediatos

### Paso 1: Validación del Plan (AHORA)
- ¿Este plan tiene sentido para ti?
- ¿Alguna prioridad diferente?
- ¿Restricciones de tiempo/recursos?

### Paso 2: Decisión de Implementación
Opción A: **Empezar con AlgaeBase scraper** (recomendado)
- Mayor impacto inmediato
- Información crítica para identificación

Opción B: **Arreglar PubMed primero**
- Más rápido de implementar
- Menor impacto pero útil

Opción C: **Consolidación de datos existentes**
- Crear estructura unificada primero
- Más ordenado pero menos valor inmediato

---

## 💡 Recomendación Final

**MI RECOMENDACIÓN**: Implementar en este orden:

1. **Día 1**: Crear dataset maestro unificado + estructura de directorios
2. **Días 2-3**: Scraper de AlgaeBase (máximo valor)
3. **Día 4**: Mejorar PubMed (buscar abstracts, cascada de búsquedas)
4. **Día 5**: Sistema de imágenes básico (Wikipedia/Wikimedia)
5. **Día 6-7**: Consolidación en knowledge base JSON estructurado
6. **Día 8+**: Vector DB y preparación para RAG

Con este plan tendrás una base de conocimientos realmente robusta y útil para tu sistema RAG de identificación de algas.

---

## 📞 ¿Qué Quieres Hacer?

Dime:
1. ¿Te parece bien este plan?
2. ¿Quieres que empiece a implementar algo específico?
3. ¿Necesitas más detalles de alguna parte?
4. ¿Tienes restricciones o preferencias que deba considerar?

¡Estoy listo para empezar a codificar! 🚀
