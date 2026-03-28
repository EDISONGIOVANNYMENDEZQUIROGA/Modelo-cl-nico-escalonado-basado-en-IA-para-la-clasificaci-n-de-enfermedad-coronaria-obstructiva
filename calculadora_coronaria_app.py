
"""
Calculadora clínica escalonada para sospecha de enfermedad coronaria
Autor: Edison Giovanny Mendez Quiroga
Uso:
    streamlit run calculadora_coronaria_app.py

Esta aplicación implementa los scores definidos en el TFM y sugiere
el siguiente paso diagnóstico según la probabilidad estimada.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import streamlit as st


# =========================
# Funciones de transformación
# =========================

def age_risk_group(age: int, sex: str) -> int:
    """
    Hombres:
        0: <40
        1: 40-60
        2: 61-70
        3: >70
    Mujeres:
        0: <50
        1: 50-60
        2: 61-70
        3: >70
    """
    sex = sex.lower()
    if sex == "hombre":
        if age < 40:
            return 0
        elif age <= 60:
            return 1
        elif age <= 70:
            return 2
        return 3

    if age < 50:
        return 0
    elif age <= 60:
        return 1
    elif age <= 70:
        return 2
    return 3


def cp_risk_score(cp: int) -> int:
    """
    1: angina típica -> 3
    2: angina atípica -> 2
    3: dolor no anginoso -> 1
    4: asintomático -> 0
    """
    mapping = {1: 3, 2: 2, 3: 1, 4: 0}
    return mapping[cp]


def trestbps_category(trestbps: int) -> int:
    """
    <130 -> 0
    130-139 -> 1
    140-159 -> 2
    >=160 -> 3
    """
    if trestbps < 130:
        return 0
    elif trestbps <= 139:
        return 1
    elif trestbps <= 159:
        return 2
    return 3


def score1_category(score1_raw: int) -> int:
    """
    0-3 -> 0 baja
    4-6 -> 1 intermedia
    7-9 -> 2 alta
    """
    if score1_raw <= 3:
        return 0
    elif score1_raw <= 6:
        return 1
    return 2


def restecg_points(restecg: int) -> int:
    """
    0 normal
    1 alteración ST-T
    2 HVI
    """
    return restecg


def score2_interpretation(score2: int) -> str:
    if score2 == 0:
        return "Baja probabilidad"
    elif score2 in (1, 2):
        return "Alta probabilidad"
    return "Muy alta probabilidad"


def fbs_points(diabetes_fbs: bool) -> int:
    return 1 if diabetes_fbs else 0


def chol_category(chol: int) -> int:
    """
    <200 -> 0
    200-239 -> 1
    >=240 -> 2
    """
    if chol < 200:
        return 0
    elif chol <= 239:
        return 1
    return 2


def score3_interpretation(score3: int) -> str:
    if score3 == 0:
        return "Baja probabilidad"
    elif 1 <= score3 <= 3:
        return "Alta probabilidad"
    return "Muy alta probabilidad"


def thalach_performance(age: int, thalach: int) -> int:
    """
    0 adecuado/normal >=85% de la FC máxima teórica
    1 anormal <85%
    """
    theoretical_max = max(1, 220 - age)
    ratio = thalach / theoretical_max
    return 0 if ratio >= 0.85 else 1


def oldpeak_ischemia(oldpeak: float) -> int:
    """
    0 si <1 mm
    1 si >=1 mm
    """
    return 1 if oldpeak >= 1.0 else 0


def slope_risk(slope: int) -> int:
    """
    slope original:
    1 descendente
    2 plano
    3 ascendente

    nuevo:
    ascendente -> 0
    plano -> 1
    descendente -> 2
    """
    mapping = {3: 0, 2: 1, 1: 2}
    return mapping[slope]


def score4_interpretation(score4: int) -> str:
    if score4 <= 2:
        return "Baja probabilidad"
    elif score4 <= 6:
        return "Alta probabilidad"
    return "Muy alta probabilidad"


def thal_category(thal: int) -> int:
    """
    3 normal -> 0
    7 defecto reversible -> 1
    6 defecto fijo -> 2
    """
    mapping = {3: 0, 7: 1, 6: 2}
    return mapping[thal]


def ca_category(ca: int) -> int:
    return ca


# =========================
# Modelo de decisión
# =========================

@dataclass
class PatientData:
    age: int
    sex: str
    cp: int
    trestbps: int
    restecg: int
    fbs_diabetes: bool
    chol: int
    can_exercise: bool
    thalach: Optional[int] = None
    exang: Optional[int] = None
    oldpeak: Optional[float] = None
    slope: Optional[int] = None
    thal: Optional[int] = None
    ca: Optional[int] = None


def calculate_all_scores(data: PatientData) -> Dict[str, object]:
    age_group = age_risk_group(data.age, data.sex)
    cp_score = cp_risk_score(data.cp)
    tas_cat = trestbps_category(data.trestbps)

    score1_raw = age_group + cp_score + tas_cat
    score1 = score1_category(score1_raw)

    s2 = score1 + restecg_points(data.restecg)
    s2_interp = score2_interpretation(s2)

    s3 = s2 + fbs_points(data.fbs_diabetes) + chol_category(data.chol)
    s3_interp = score3_interpretation(s3)

    result = {
        "age_risk_group": age_group,
        "cp_risk_score": cp_score,
        "trestbps_category": tas_cat,
        "score1_raw": score1_raw,
        "score1": score1,
        "score1_interpretation": {
            0: "Baja probabilidad presuntiva",
            1: "Probabilidad intermedia",
            2: "Alta probabilidad presuntiva",
        }[score1],
        "score2": s2,
        "score2_interpretation": s2_interp,
        "score3": s3,
        "score3_interpretation": s3_interp,
    }

    s2_or_s3_high = (s2_interp in ("Alta probabilidad", "Muy alta probabilidad")) or (
        s3_interp in ("Alta probabilidad", "Muy alta probabilidad")
    )

    if not s2_or_s3_high:
        result["next_step"] = "No indicar prueba de esfuerzo, gammagrafía ni cateterismo de entrada."
        result["clinical_path"] = (
            "Paciente de baja probabilidad en scores presuntivos. "
            "Se sugiere manejo conservador, control clínico y búsqueda de causas no coronarias."
        )
        return result

    if data.can_exercise:
        if None not in (data.thalach, data.exang, data.oldpeak, data.slope):
            s4 = (
                s3
                + thalach_performance(data.age, data.thalach)
                + int(data.exang)
                + oldpeak_ischemia(float(data.oldpeak))
                + slope_risk(int(data.slope))
            )
            s4_interp = score4_interpretation(s4)
            result["score4"] = s4
            result["score4_interpretation"] = s4_interp

            if s4 <= 2:
                result["next_step"] = "Manejo conservador y seguimiento clínico."
                result["clinical_path"] = (
                    "Prueba de esfuerzo con resultado de baja probabilidad. "
                    "No se sugiere gammagrafía ni cateterismo de rutina."
                )
            elif 3 <= s4 <= 6:
                result["next_step"] = "Indicar gammagrafía miocárdica (Score 5)."
                result["clinical_path"] = (
                    "Prueba de esfuerzo en zona intermedia/alta. "
                    "Se recomienda imagen funcional para afinar la estratificación."
                )
            else:
                result["next_step"] = "Valorar cateterismo cardíaco (Score 6)."
                result["clinical_path"] = (
                    "Prueba de esfuerzo muy sugestiva de enfermedad coronaria. "
                    "Se justifica estudio anatómico invasivo según contexto clínico."
                )
        else:
            result["next_step"] = "Completar variables de prueba de esfuerzo para calcular Score 4."
            result["clinical_path"] = (
                "El paciente podría realizar prueba de esfuerzo, pero faltan datos para interpretarla."
            )
    else:
        result["next_step"] = "Indicar gammagrafía miocárdica (Score 5)."
        result["clinical_path"] = (
            "Paciente con score presuntivo alto o muy alto que no puede realizar esfuerzo. "
            "Se recomienda gammagrafía como prueba funcional alternativa."
        )

    if data.thal is not None:
        s5 = s3 + thal_category(data.thal)
        result["score5"] = s5
        result["score5_component_thal"] = thal_category(data.thal)

    if data.ca is not None:
        s6 = s3 + ca_category(data.ca)
        result["score6"] = s6
        result["score6_component_ca"] = ca_category(data.ca)

    if (
        None not in (data.thalach, data.exang, data.oldpeak, data.slope)
        and data.thal is not None
        and data.ca is not None
    ):
        s7 = (
            s3
            + thalach_performance(data.age, data.thalach)
            + int(data.exang)
            + oldpeak_ischemia(float(data.oldpeak))
            + slope_risk(int(data.slope))
            + thal_category(data.thal)
            + ca_category(data.ca)
        )
        result["score7"] = s7
        result["score7_interpretation"] = (
            "Score integral total con máxima información clínica, funcional y anatómica."
        )

    return result


# =========================
# Interfaz Streamlit
# =========================

st.set_page_config(page_title="Calculadora coronaria escalonada", layout="wide")
st.title("Calculadora clínica escalonada de enfermedad coronaria")
st.caption(
    "Basada en el modelo del TFM de Edison Giovanny Mendez Quiroga. "
    "La app sugiere el siguiente paso diagnóstico y aporta una interpretación clínica orientativa."
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Datos clínicos básicos")
    age = st.number_input("Edad", min_value=18, max_value=105, value=55, step=1)
    sex = st.selectbox("Sexo", ["Hombre", "Mujer"])
    cp = st.selectbox(
        "Dolor torácico",
        options=[1, 2, 3, 4],
        format_func=lambda x: {
            1: "1 = Angina típica",
            2: "2 = Angina atípica",
            3: "3 = Dolor no anginoso",
            4: "4 = Asintomático",
        }[x],
    )
    trestbps = st.number_input("Presión arterial sistólica (mmHg)", min_value=80, max_value=250, value=135)
    restecg = st.selectbox(
        "ECG en reposo",
        options=[0, 1, 2],
        format_func=lambda x: {
            0: "0 = Normal",
            1: "1 = Alteraciones ST-T",
            2: "2 = Hipertrofia ventricular izquierda",
        }[x],
    )
    fbs_diabetes = st.checkbox("Glucemia en ayunas compatible con diabetes (≥126 mg/dL)")
    chol = st.number_input("Colesterol total (mg/dL)", min_value=50, max_value=700, value=210)

with col2:
    st.subheader("Capacidad funcional y pruebas complementarias")
    can_exercise = st.checkbox("El paciente puede realizar prueba de esfuerzo", value=True)

    st.markdown("**Si hay datos de prueba de esfuerzo:**")
    thalach = st.number_input("Frecuencia cardíaca máxima alcanzada", min_value=40, max_value=250, value=150)
    exang = st.selectbox(
        "Angina inducida por esfuerzo",
        options=[0, 1],
        format_func=lambda x: {
            0: "0 = No",
            1: "1 = Sí",
        }[x],
    )
    oldpeak = st.number_input("Depresión del ST (oldpeak)", min_value=0.0, max_value=10.0, value=1.0, step=0.1)
    slope = st.selectbox(
        "Pendiente del ST (slope)",
        options=[1, 2, 3],
        format_func=lambda x: {
            1: "1 = Descendente",
            2: "2 = Plano",
            3: "3 = Ascendente",
        }[x],
    )

    st.markdown("**Si ya hay gammagrafía o cateterismo:**")
    has_thal = st.checkbox("Ingresar gammagrafía (thal)")
    thal = None
    if has_thal:
        thal = st.selectbox(
            "Resultado gammagrafía (thal)",
            options=[3, 7, 6],
            format_func=lambda x: {
                3: "3 = Normal",
                7: "7 = Defecto reversible",
                6: "6 = Defecto fijo",
            }[x],
        )

    has_ca = st.checkbox("Ingresar cateterismo (ca)")
    ca = None
    if has_ca:
        ca = st.selectbox("Número de vasos afectados (ca)", options=[0, 1, 2, 3])

if st.button("Calcular scores y sugerir siguiente paso", type="primary"):
    data = PatientData(
        age=int(age),
        sex=sex,
        cp=int(cp),
        trestbps=int(trestbps),
        restecg=int(restecg),
        fbs_diabetes=bool(fbs_diabetes),
        chol=int(chol),
        can_exercise=bool(can_exercise),
        thalach=int(thalach) if can_exercise else None,
        exang=int(exang) if can_exercise else None,
        oldpeak=float(oldpeak) if can_exercise else None,
        slope=int(slope) if can_exercise else None,
        thal=int(thal) if thal is not None else None,
        ca=int(ca) if ca is not None else None,
    )

    result = calculate_all_scores(data)

    st.subheader("Resultados")
    c1, c2, c3 = st.columns(3)
    c1.metric("Score 1", f"{result['score1']} ({result['score1_interpretation']})")
    c2.metric("Score 2", f"{result['score2']} ({result['score2_interpretation']})")
    c3.metric("Score 3", f"{result['score3']} ({result['score3_interpretation']})")

    if "score4" in result:
        st.metric("Score 4", f"{result['score4']} ({result['score4_interpretation']})")
    if "score5" in result:
        st.metric("Score 5", f"{result['score5']}")
    if "score6" in result:
        st.metric("Score 6", f"{result['score6']}")
    if "score7" in result:
        st.metric("Score 7", f"{result['score7']}")

    st.subheader("Siguiente paso sugerido")
    st.success(result["next_step"])

    st.subheader("Interpretación clínica")
    st.write(result["clinical_path"])

    with st.expander("Ver componentes calculados"):
        st.json(result)

st.markdown("---")
st.markdown(
    "**Aviso:** esta calculadora es un prototipo académico para apoyo a la decisión clínica y "
    "no sustituye el juicio médico, las guías vigentes ni la valoración individual del paciente."
)
