# =============================================================================
# prompt.py — TARA generation prompt template
# =============================================================================

TARA_PROMPT_TEMPLATE = """
As a cybersecurity expert in the automotive domain (ISO 21434), analyze the provided context to generate a structured TARA (Threat Analysis and Risk Assessment) model in JSON format.

### SOURCES OF INFORMATION:
{% for doc in documents %}
SOURCE: {{ doc.meta.source }} (File: {{ doc.meta.file or 'N/A' }}, Type: {{ doc.meta.type or 'N/A' }})
CONTENT:
{{ doc.content }}
---
{% endfor %}

### USER QUERY:
{{ question }}

### YOUR TASK:
1.  **Synthesize**: Based on the retrieved chunks from `dataecu.json` (ECU Specs) and `reports_db` (Reference reports/hierarchies/edges), identify the core components, their security properties, and potential damage scenarios relevant to the query.
2.  **Accuracy over Replication**: Do not simply copy a single reference report. Instead, use the retrieved information to build a high-quality model specifically for the requested system.
3.  **Graph Constraints**:
    *   `nodes`: Every node MUST have unique `position` (x, y) coordinates. Spread them out logically (e.g., Groups at the back, assets inside or nearby). No node should be at (0,0).
    *   `edges`: Every edge MUST have a real `source` and `target` matching the `id` of a defined node. 
4.  **Formatting**: The output MUST be a single valid JSON object.
- REPORTS_DB entries show real reference architectures. If the TARGET SYSTEM matches a REPORTS_DB system
  (e.g. query is "BMS" and a BMS reference exists), follow the reference architecture's exact component names,
  hierarchy, edge labels, and structure as closely as possible.
- For other systems, use REPORTS_DB entries as structural EXAMPLES ONLY for JSON shape and patterns.
- Do NOT reproduce another system's component names unless the TARGET SYSTEM matches exactly.
- Use realistic automotive architecture relevant to the TARGET SYSTEM only.
- Prefer knowledge retrieved from cybersecurity context (ISO 21434, CWE, CAPEC, MITRE, ATM).
- If information is missing, infer only common industry-standard components for the specified system.

Threat reasoning must follow:
CWE (root weakness) → CAPEC (attack pattern) → MITRE ATT&CK technique → ATM relevance → Damage Scenario

-------------------------------------------------

SYSTEM REQUEST:
{{question}}

{% if ecu_spec %}
AUTHORITATIVE SYSTEM SPECIFICATION (dataecu.json):
{{ecu_spec}}
{% endif %}

{% if reference_report %}
REFERENCE TARA REPORT (REPORTS_DB):
{{reference_report}}
{% endif %}

CYBERSECURITY KNOWLEDGE CONTEXT:
{% for doc in documents %}
[{{ doc.meta.source }}{% if doc.meta.section_id is defined %} § {{ doc.meta.section_id }}{% endif %}{% if doc.meta.type is defined %} | {{ doc.meta.type }}{% endif %}]
{{ doc.content }}
---
{% endfor %}

-------------------------------------------------

ARCHITECTURE RULES

The architecture uses a nested group/container hierarchy:

1. GROUP NODES (type:"group") are invisible containers that establish parent-child hierarchy.
   - The top-level system (e.g. "Battery Management System") is a group with parentId:null.
   - Sub-systems (e.g. MCU block) are groups nested inside the top-level group.
   - Group nodes have a dashed-border style, NOT a solid backgroundColor.

2. DEFAULT NODES (type:"default") are visible components (CellMonitoring, Code Flash, etc.).
   - Each default node has a parentId pointing to its containing group.
   - External entities (BatteryPack, Vehicle System, Cloud) have parentId:null (outside the system group).

3. DATA NODES (type:"data") are small circular data items (SoC, SoH).
   - These are small (width:50, height:30) and have parentId pointing to their containing group.

4. PARENTID HIERARCHY: Every node must have a parentId.
   - parentId:null means the node is at the top level (external entities and the main system group).
   - Components inside the system group have parentId = the system group's id.
   - Components inside a sub-group (e.g. MCU) have parentId = the sub-group's id.

5. EDGES: Each edge must have a "data.label" that is a SHORT protocol/interface name:
   - CORRECT: "SPI", "CAN1", "CAN2", "IO_PINS", "Vehicle CAN", "Internet", "ICD_Data"
   - WRONG: "Measurements", "CAN Communication", "Controls Power Flow", "Sends data to"

6. COLOR CODING: Assign distinct backgroundColor values by component role:
   - Monitoring/sensing: yellow shades (#e6df19, #accd32)
   - I/O interfaces: beige/tan (#e2dfc1)
   - Flash/storage: purple (#ccc8ea)
   - Security (Keys, Certificates): green (#51dc1e, #62c945)
   - Debug: red/orange (#e26a6a)
   - Data items (SoC, SoH): light yellow (#e3e896)
   - External/generic: gray (#dadada)

-------------------------------------------------

TASK

1. Identify the architecture of the requested system (use the AUTHORITATIVE ASSET LIST if provided).
2. Generate assets that belong strictly to the TARGET SYSTEM — no others.
3. Use group containers for system/sub-system hierarchy with correct parentId references.
4. Create architecture relationships (edges) with short protocol/interface labels.
5. Generate realistic cybersecurity damage scenarios referencing only the generated assets.
6. For each damage scenario derive an Impact Rating using SFOP categories.

-------------------------------------------------

IMPACT RATING SCALE

For every damage scenario derive cyber losses using SFOP categories:
Safety | Financial | Operational | Privacy

For each cyber loss assign: Negligible | Minor | Moderate | Major | Severe
Then derive an overall impact rating based on the highest impact.

-------------------------------------------------

STRICT OUTPUT FORMAT

Return ONLY valid JSON. Do not include explanations, markdown fences, or prose.
Start the response with '{'.

Return JSON exactly in this structure (showing all three node types):

{
 "assets":{
   "_id":"",
   "user_id":"",
   "model_id":"",
   "template":{
      "nodes":[
         {
           "id":"<system-group-uuid>",
           "type":"group",
           "parentId":null,
           "data":{
             "label":"System Name",
             "nodeCount":7,
             "style":{"background":"rgba(33,150,243,0.05)","border":"1px dashed #2196F3","borderRadius":"8px","boxShadow":"0 2px 6px rgba(0,0,0,0.1)","height":510,"width":1041}
           },
           "properties":["Integrity","Authenticity"],
           "style":{"width":1041,"height":510},
           "position":{"x":,"y":},
           "positionAbsolute":{"x":,"y":},
           "width":1041,
           "height":510,
           "zIndex":0
         },
         {
           "id":"<component-uuid>",
           "type":"default",
           "parentId":"<system-group-uuid>",
           "isAsset":false,
           "data":{
             "label":"ComponentName",
             "description":"",
             "style":{"backgroundColor":"#dadada","borderColor":"gray","borderStyle":"solid","borderWidth":"2px","color":"black","fontFamily":"Inter","fontSize":"12px","fontWeight":500,"height":50,"width":150}
           },
           "properties":["Integrity","Confidentiality","Availability"],
           "style":{"width":150,"height":50},
           "position":{"x":,"y":},
           "positionAbsolute":{"x":,"y":},
           "width":150,
           "height":50
         },
         {
           "id":"<data-item-uuid>",
           "type":"data",
           "parentId":"<system-group-uuid>",
           "isAsset":false,
           "data":{
             "label":"SoC",
             "style":{"backgroundColor":"#e3e896","borderColor":"gray","borderStyle":"solid","borderWidth":"2px","color":"black","fontFamily":"Inter","fontSize":"12px","fontWeight":500,"height":30,"width":50}
           },
           "properties":["Authenticity","Integrity"],
           "style":{"width":50,"height":30},
           "position":{"x":,"y":},
           "positionAbsolute":{"x":,"y":},
           "width":50,
           "height":30
         }
      ],
      "edges":[
         {
           "id":"",
           "source":"<source node id>",
           "target":"<target node id>",
           "sourceHandle":"b",
           "targetHandle":"left",
           "type":"step",
           "animated":true,
           "markerEnd":{"color":"#64B5F6","height":18,"type":"arrowclosed","width":18},
           "markerStart":{"color":"#64B5F6","height":18,"orient":"auto-start-reverse","type":"arrowclosed","width":18},
           "style":{"end":true,"start":true,"stroke":"#808080","strokeDasharray":"0","strokeWidth":2},
           "properties":["Integrity"],
           "data":{"label":"SPI","offset":0,"t":0.5}
         }
      ],
      "details":[
      {
      "nodeId":"<must match node id>",
      "name":"<must match node label>",
      "desc":"<asset description>",
      "type":"default",
      "props":[
      {"name":"Integrity","id":""},
      {"name":"Confidentiality","id":""},
      {"name":"Authenticity","id":""},
      {"name":"Authorization","id":""},
      {"name":"Availability","id":""},
      {"name":"Non-repudiation","id":""}
    ]
   }
   ]
   }
 },
 "damage_scenarios":{
   "_id":"",
   "model_id":"",
   "type":"damage",
   "Derivations":[
      {
        "id":"","nodeId":"","task":"Threat Analysis",
        "name":"","loss":"","asset":"",
        "damage_scene":"","isChecked":false
      }
   ],
   "Details":[
      {
        "Name":"",
        "Description":"",
        "cyberLosses":[{"id":"","name":"","node":"","nodeId":"","isSelected":true,"is_risk_added":false}],
        "impacts":{"Financial Impact":"","Safety Impact":"","Operational Impact":"","Privacy Impact":""},
        "key":1,
        "_id":""
      }
   ]
 }
}

-------------------------------------------------

CONSTRAINTS

- Generate ONLY the assets listed in the AUTHORITATIVE ASSET LIST (if provided), or assets strictly belonging to the TARGET SYSTEM.
- Do NOT add components from other ECU systems.
- Use group containers (type:"group") for system and sub-system boundaries. Use type:"data" for small data nodes.
- Most component nodes should have isAsset:false unless they are explicitly identified as security assets.
- Edge labels MUST be short protocol/interface names (SPI, CAN1, IO_PINS), NOT descriptive phrases.
- Assign meaningful backgroundColor values per component role, not all gray.
- LAYOUT: Assign realistic, non-zero x/y coordinates so nodes are spread out logically (e.g. x: 100-1000, y: 50-600). nodes MUST NOT overlap.
- parentId must correctly reflect the hierarchy: external entities → null, components → their group id.
- Damage scenarios must reference valid nodeId values from the nodes above.
- Impact rating must be derived from the damage scenario context.
- Use threat reasoning from CWE, MITRE, CAPEC, ATM — not from REPORTS_DB examples.
"""

# =============================================================================
# specialized prompts for multi-agent flow
# =============================================================================

# 0. SDD ANALYST AGENT (The Technical Preparer)
SDD_ANALYST_PROMPT = """
As a Senior Automotive System Designer (OEM/Tier-1), write a HIGH-PRECISION System Design Document (SDD) for the requested system: {{question}}.
Your goal is to match the technical depth and structured clarity of an industry-standard OEM specification.

### MANDATORY SDD STRUCTURE (MATCH MENTOR-GRADE TECHNICALITY):

1. **System Context (Item Definition)**: Define the context and ASIL safety level (B/C/D) based on ISO 26262.
2. **Functional Blocks**: Identify specific functional managers. 
   - *Example for AIS*: HMI Manager, Connectivity Manager, Media Manager, Security Manager, OTA Manager.
   - *Example for ADAS*: Perception Module, Planning Block, Actuator Controller.
3. **Internal vs. External Interfaces**:
   - **Internal**: Use Serial (MIPI CSI, I2C, SPI) for sub-block communication.
   - **External**: Use CAN1 (Control/Signals), CAN2 (Diagnostics/UDS), and Automotive Ethernet (SOME/IP).
4. **Data Categories**: Define sensitivity (Low to Critical) for User Data, Firmware, CAN-FD traffic, and Cryptographic Keys.
5. **Trust Boundaries**: Perimeters for internal modules (Trusted), Vehicle network (Semi-trusted), and Cloud (Untrusted).
6. **Threat Entry Points (Attack Surface)**: Physical (OBD-II, USB, JTAG) and Remote (Bluetooth, Wi-Fi, OTA Cloud).

### OUTPUT:
Return a HIGH-QUALITY Markdown report with detailed tables and professional technical descriptions.
"""

# 1. ARCHITECT AGENT
ARCHITECT_PROMPT = """
As a Senior Automotive Systems Architect, turn the provided SDD report into a 10/10 machine-readable TARA JSON.
Your architecture must reflect the segmentation defined in the SDD (Internal vs External Buses).

### YOUR FOCUS:
1. **Node Depth**: Every "Functional Manager" in the SDD must be a node (type:"default") in the JSON.
2. **Bus Segmentation**: Draw separate edges for CAN1 (Control) and CAN2 (Diagnostics) as defined in the SDD.
3. **Security Details**: For every sensitive asset (HMI, Keys, OTA), fill the 'details' list with security properties (Integrity, Authenticity).
4. **Organic Visual Layout**: Avoid grids; use a natural flow with +/- 10px random jitter.

### INPUT:
- SDD Report: {{sdd_report}}

### OUTPUT SCHEMA:
Return ONLY a valid JSON object. Do NOT include markdown fences or prose.

{
  "assets": {
    "template": {
      "nodes": [
        {"id": "node1", "type": "default", "parentId": "group1", "position": {"x": 124, "y": 257}, "data": {"label": "Manager Name", ...}, ...}
      ],
      "edges": [
        {"source": "node1", "target": "node2", "label": "CAN1", "properties": ["Integrity"], ...}
      ],
      "details": [
        {"nodeId": "node1", "name": "Manager Name", "type": "default", "props": [{"name": "Integrity", "id": ""}]}
      ]
    }
  }
}
"""

# 2. THREAT ANALYST AGENT
THREAT_PROMPT = """
As a Cybersecurity Threat Analyst, perform "Pin-Point Pinning."
Threats MUST NOT just target the whole ECU; they should target the specific SUB-BLOCK (e.g., OTA Manager) and DATA (Firmware) identified in the SDD and JSON.

### INPUT:
- System Architecture JSON: {{architecture}}
- SDD Context: {{sdd_report}}

### YOUR FOCUS:
1. Reference the exact 'nodeId' of the sub-blocks (e.g., ota_manager).
2. Follow the chain: CWE -> CAPEC -> MITRE for every sub-block attack.
"""

# 3. DAMAGE ANALYST AGENT
DAMAGE_PROMPT = """
As a Damage Assessment Specialist, your task is to evaluate the impact of the identified threats.
Assign Cyber Losses and SFOP Impact Ratings (Safety, Financial, Operational, Privacy).

### INPUT:
- Threats: {{threats}}
- Architecture: {{architecture}}

### YOUR FOCUS:
1. For each threat, define the specific 'Details' including cyberLosses and impacts.
2. Impacts must be one of: Negligible | Minor | Moderate | Major | Severe.
3. Ensure 'nodeId' matches the architecture.

### OUTPUT:
Return ONLY a valid JSON object containing the "Details" list.

{
  "Details": [
    {
      "Name": "Scenario Name",
      "Description": "Impact description",
      "cyberLosses": [{"id": "uuid", "name": "loss name", "node": "asset name", "nodeId": "id-from-arch", "isSelected": true}],
      "impacts": {"Financial Impact": "...", "Safety Impact": "...", "Operational Impact": "...", "Privacy Impact": "..."},
      "key": 1,
      "_id": "uuid"
    },
    ...
  ]
}
"""


