# CONTEXTO DE DOMINIO: SECTOR INMOBILIARIO EN ARGENTINA

Este documento define la lógica de negocio, reglas financieras, legales y
terminología del mercado inmobiliario argentino para la configuración de un
agente conversacional. Vive en `/knowledge` porque es exactamente el tipo de
archivo que la Fase 2 de `CLAUDE.md` (Pregunta 7) espera que el usuario
coloque aquí — Claude Code lo lee y lo incorpora al system prompt.

---

## 1. TERMINOLOGÍA Y CONCEPTOS CLAVE

* **Tipologías:**
  * **PH (Propiedad Horizontal):** Viviendas divididas bajo régimen de propiedad horizontal pero habitualmente sin expensas o con expensas muy bajas, sin ascensor ni grandes áreas comunes.
  * **Departamento / Piso / Semipiso:** "Piso" indica un departamento por planta; "Semipiso", dos por planta.
  * **Ambientes:** En Argentina las propiedades se miden por "ambientes" (ej. 2 ambientes = 1 dormitorio + 1 living/comedor). La cocina y el baño no cuentan como ambientes.
  * **Studio / Monoambiente:** Propiedad de un solo espacio integrable.

* **Superficies:**
  * **Cubierta (m²):** Espacio bajo techo.
  * **Semicubierta (m²):** Balcones techados, galerías.
  * **Descubierta (m²):** Patios, terrazas al aire libre.
  * **M² Computable / Ponderado:** Varía según la tasación, pero estándar habitual: 100% Cubierta + 50% Semicubierta + 10% a 30% Descubierta.

* **Gastos y Transacción:**
  * **Expensas Ordinarias:** Gastos habituales de mantenimiento del edificio (habitualmente a cargo del inquilino).
  * **Expensas Extraordinarias:** Fondos de reserva o arreglos estructurales del edificio (a cargo del propietario).
  * **Reserva:** Entrega de dinero para congelar la oferta y elevar la propuesta formal al propietario.
  * **Boleto de Compraventa:** Contrato privado previo a la escritura donde se compromete la venta y se suele abonar un porcentaje (ej. 30%-50%).
  * **Escritura Traslativa de Dominio:** Acto formal ante escribano público que otorga la titularidad.

---

## 2. ASPECTOS LEGALES Y CONTRATACIÓN (Post-DNU 70/2023)

* **Alquileres Habitacionales:**
  * **Moneda:** Libre acuerdo entre partes (USD, ARS, etc.).
  * **Plazo de Contrato:** Libre acuerdo. Si no se especifica, el plazo legal supletorio es de 2 años.
  * **Ajuste de Precio:** Libre acuerdo en periodicidad (mensual, cuatrimestral, semestral) e índice (IPC - Índice de Precios al Consumidor, ICL - Índice para Contratos de Alquiler, CAC - Cámara Argentina de la Construcción).
  * **Garantías Habituales:**
    * Garantía propietaria (inmueble de familiar directo, preferentemente en la misma jurisdicción).
    * Seguros de caución (Finaer, Premium Group, GaranteCO, Banco Ciudad).
    * Recibos de sueldo / Demostración de ingresos (habitualmente se pide que el alquiler no supere el 30%-35% del ingreso).

---

## 3. VALORACIÓN Y DINÁMICA DE PRECIOS

* **Moneda de Operación:**
  * **Venta:** Prácticamente 100% dolarizada (USD billete físico en mano o transferencia MEP según acuerdos).
  * **Alquileres:** Mixto (ARS ajustados por inflación o USD en zonas de alta demanda/turísticas).

* **Indicadores de Tasación Promedio (Referenciales CABA - ajustar según zona/barrio):**
  * El valor del m² varía drásticamente según el barrio (ej. Puerto Madero, Palermo, Recoleta vs. Flores, Balvanera, Lugano).
  * Rango de margen de negociación habitual en compraventa: 5% al 10% de contraoferta sobre precio publicado.

---

## 4. ROL Y TONO DEL AGENTE

* **Perfil:** Asesor inmobiliario profesional, empático, conocedor de la realidad económica local, claro y directo.
* **Manejo de Dudas:** Al responder sobre costos, especificar siempre si los valores son en USD o Pesos Argentinos (ARS) y aclarar qué tipo de cotización o ajuste aplica cuando sea relevante.

---

## 5. FUENTES DE DATOS DE MERCADO EN TIEMPO REAL

> **Nota de arquitectura:** por ahora estas fuentes quedan como contexto
> estático (el agente las conoce y las puede mencionar, pero NO tiene
> acceso en vivo a internet). La integración en tiempo real (consultar el
> índice actualizado, buscar comparables reales) la va a resolver un
> agente/servicio aparte más adelante — cuando esté listo, se conecta como
> una tool nueva en `agent/tools.py` (ej. `consultar_precio_mercado()`),
> sin tocar `brain.py` ni el resto del sistema.

* **ZonaProp — ZP Index** ([zonaprop.com.ar/blog/zpindex](https://www.zonaprop.com.ar/blog/zpindex/)):
  índice de precio promedio por m² segmentado por zona/barrio y tipo de
  propiedad (monoambiente, 2 amb, 3 amb...), para CABA, GBA, Rosario y
  Córdoba, tanto venta como alquiler, en USD/m² para CABA. Se actualiza
  mensual/trimestral/anual. Es la referencia a usar cuando un cliente
  pregunte si un precio "está en línea con el mercado" de una zona.
* **ArgenProp, ZonaProp, MercadoLibre Inmuebles:** portales de referencia
  para comparables (propiedades similares publicadas por terceros) — a
  futuro complementan el catálogo propio (`config/propiedades.yaml`) para
  responder "qué hay parecido en la zona" más allá del stock propio del
  negocio.

Si un cliente pregunta por precios de mercado o comparables y el agente no
tiene esa tool todavía, debe decir que no tiene acceso a cotizaciones en
vivo y ofrecer conectarlo con el equipo — nunca inventar un precio de
mercado.

---

## 6. COSTOS DE ESCRITURACIÓN 2026 (Argentina)

Referencia aproximada — varía por provincia, por escribano, y cambia con
el tiempo. No dar un número cerrado como definitivo; aclarar que es
orientativo y que el monto final se confirma con el escribano.

* **Costo total aproximado para el comprador:** USD 5.000–6.000, ó ~5%-6%
  del valor de la propiedad (incluye honorarios de escribano, sellos,
  inscripción, aportes notariales y certificados)
* **Honorarios de escribano:** 1%-1.5% del valor de la operación en la
  mayoría de las provincias — son orientativos (el Colegio de Escribanos
  publica tablas de referencia), el monto final se negocia con el
  escribano; conviene pedir presupuesto cerrado antes de comprometerse
* **Impuesto de Sellos:** impuesto provincial/CABA sobre el instrumento
  legal; por norma se divide 50/50 entre comprador y vendedor. Varía por
  jurisdicción — ej. Salta 2% total, Provincia de Buenos Aires 3.6% del
  valor escriturado. CABA y PBA tienen exención parcial o total para
  vivienda única y permanente por debajo de un tope de valor (se
  actualiza periódicamente)
* **ITI (Impuesto a la Transferencia de Inmuebles): DEROGADO** por la Ley
  27.743 (Boletín Oficial, 8 de julio de 2024) — ya NO se paga. Si el
  agente ve o recibe información vieja que todavía lo mencione como
  vigente, no debe repetirla
* **Quién elige a quién:** el comprador elige y paga a su propio
  escribano; el vendedor puede designar el suyo, generalmente a ~50% del
  honorario del comprador

### Desglose de referencia (fuente: simulador comercial de Mudafy — orden de magnitud, no una tabla oficial)

| Concepto | Comprador | Vendedor |
|---|---|---|
| Tarifa inmobiliaria | 4% | 3% |
| Honorarios de escribanía | 2% (3.5% en primera escritura) | — |
| Gastos de escrituración | — | 2% |
| Sellos | 2.7%-3.5% (CABA), compartido | compartido |
| Fondo de reserva (solo primera escritura) | hasta 6% del valor | — |
