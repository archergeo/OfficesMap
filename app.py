import logging
from typing import List, Dict, Any, Tuple, Optional

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import yaml

# =========================
# Config do App
# =========================
st.set_page_config(page_title="CAPCO Interactive Map", page_icon="https://i0.wp.com/fresherjobinfo.in/wp-content/uploads/2022/09/CAPCO.png?resize=300%2C166&ssl=1", layout="wide")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("offices-map")

REQUIRED_FOR_MARKER = ["latitude", "longitude", "city"]
REQUIRED_FOR_CARD = ["nome", "region", "CapcoHub", "contact"]

# =========================
# Sidebar (mantemos tile selection)
# =========================
st.sidebar.title("🗺️ Mapa Style")
tile_choice = st.sidebar.selectbox(
    "Camada de mapa", 
    ["OpenStreetMap", "CartoDB positron", "Esri WorldStreetMap"],
    index=1
)
default_zoom = st.sidebar.slider("Zoom inicial", 1, 8, 3, step=1)
icon_size = st.sidebar.slider("Tamanho do ícone (px)", 24, 72, 44, step=2)

# =========================
# Utilitários
# =========================
def load_offices_from_yaml(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise ValueError("O arquivo offices.yaml deve conter uma lista de escritórios.")
    return data

def validate_records(recs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    errors, valids = [], []
    for i, r in enumerate(recs, start=1):
        missing = []
        for field in REQUIRED_FOR_MARKER + REQUIRED_FOR_CARD:
            if field not in r or pd.isna(r.get(field)):
                missing.append(field)
        if "adress" not in r and "address" not in r:
            missing.append("adress/address")
        if missing:
            errors.append(f"Item {i}: faltando campos {', '.join(missing)}")
            continue
        try:
            r["latitude"] = float(r["latitude"]); r["longitude"] = float(r["longitude"])
        except Exception:
            errors.append(f"Item {i}: latitude/longitude inválidas"); continue
        valids.append(r)
    return valids, errors

def compute_map_center(recs: List[Dict[str, Any]]) -> Tuple[float, float]:
    lats = [r["latitude"] for r in recs]; lons = [r["longitude"] for r in recs]
    return sum(lats)/len(lats), sum(lons)/len(lons)

def _is_direct_image(url: Optional[str]) -> bool:
    if not url or not isinstance(url, str): return False
    url_l = url.lower().split("?")[0]
    return url_l.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"))

def build_popup_html(r: Dict[str, Any]) -> str:
    city = r.get("city", "")
    nome = r.get("nome", "")
    region = r.get("region", "")
    hub = r.get("CapcoHub", "")
    address = r.get("adress") or r.get("address") or ""
    contact = r.get("contact", "")
    img_url = r.get("card_image_url", "")
    show_img = _is_direct_image(img_url)

    html = f"""
    <div style="font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial; width: 320px;">
      <div style="border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); overflow: hidden; border: 1px solid #e6e6e6;">
        <div style="height: 140px; background:#f6f6f6; display:flex; align-items:center; justify-content:center;">
          {('<img src="'+img_url+'" alt="office" style="max-width:100%; max-height:140px; display:block;" />') if show_img else '<div style="color:#999;">Sem imagem (use URL direta de imagem)</div>'}
        </div>
        <div style="padding: 12px 14px;">
          <div style="font-size: 14px; color:#6b7280; margin-bottom: 2px;">{city} · {region}</div>
          <div style="font-weight: 700; font-size: 16px; line-height: 1.2; margin-bottom: 8px;">{nome}</div>
          <div style="font-size: 13px; color:#111827; margin-bottom: 6px;">📍 {address}</div>
          <div style="font-size: 13px; color:#111827; margin-bottom: 6px;">☎️ {contact}</div>
          <div style="margin-top: 8px;">
            <a href="{hub}" target="_blank" rel="noopener noreferrer" style="text-decoration:none; font-size: 13px; font-weight:600; color:#2563eb;">Abrir CapcoHub →</a>
          </div>
        </div>
      </div>
    </div>
    """
    return html

def build_round_logo_divicon(logo_url: Optional[str], size: int) -> folium.DivIcon:
    """
    Ícone redondo via DivIcon usando <img> com border-radius:50%.
    Se logo_url não for válida, renderiza um círculo cinza.
    """
    diameter = size
    radius = diameter // 2
    if logo_url and _is_direct_image(logo_url):
        html = f'''
        <div style="width:{diameter}px;height:{diameter}px;border-radius:50%;
                    overflow:hidden; box-shadow:0 0 0 2px rgba(0,0,0,0.12), 0 6px 14px rgba(0,0,0,0.2);">
          <img src="{logo_url}" style="width:100%;height:100%;object-fit:cover;display:block;" />
        </div>
        '''
    else:
        html = f'''
        <div style="width:{diameter}px;height:{diameter}px;border-radius:50%;
                    background:#c4c4c4; box-shadow:0 0 0 2px rgba(0,0,0,0.12), 0 6px 14px rgba(0,0,0,0.2);">
        </div>
        '''
    # anchor centralizado
    return folium.DivIcon(html=html, icon_size=(diameter, diameter), icon_anchor=(radius, radius), class_name="capco-round-icon")

# =========================
# Execução principal
# =========================
st.title("🌍 CAPCO Offices — Interactive Map")

try:
    records = load_offices_from_yaml("data/offices.yaml")
except Exception as e:
    st.error(f"Erro ao ler data/offices.yaml: {e}")
    st.stop()

valids, errs = validate_records(records)
if errs:
    with st.expander("⚠️ Problemas encontrados no arquivo (itens ignorados)", expanded=False):
        for e in errs: st.write(f"- {e}")
if not valids:
    st.error("Nenhum escritório válido encontrado."); st.stop()

center_lat, center_lon = compute_map_center(valids)
m = folium.Map(location=[center_lat, center_lon], zoom_start=default_zoom, tiles=tile_choice)

for rec in valids:
    popup_html = build_popup_html(rec)
    popup = folium.Popup(popup_html, max_width=360, min_width=320)

    icon_url = rec.get("icon_image_url")
    div_icon = build_round_logo_divicon(icon_url, icon_size)
    tooltip = f"{rec.get('city', '')} · {rec.get('nome', '')}"

    folium.Marker(
        location=[rec["latitude"], rec["longitude"]],
        popup=popup,
        tooltip=tooltip,
        icon=div_icon
    ).add_to(m)

st_folium(m, width="100%", height=700)
