from pathlib import Path

from openpyxl import Workbook

from ai_store_support.db import create_database
from ai_store_support.normalization import split_model_group
from ai_store_support.service import PhoneModelService


def make_service(tmp_path: Path) -> PhoneModelService:
    engine, session_factory = create_database(tmp_path / "test.db")
    return PhoneModelService(session_factory, engine)


def create_source(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "型号明细"
    ws.append(["材质", "品牌栏目", "型号组合", "库存状态"])
    ws.append(["FL二合一磨砂二代", "VIVO", "VIVOY100/VIVOY100I", "未标注"])
    ws.append(["FL液态直边软壳", "VIVO", "VIVOY100", "待到货"])
    ws.append(["FL二合一磨砂二代", "苹果", "苹果15/15PRO通用", "未标注"])
    wb.save(path)


def test_import_and_exact_material_query(tmp_path: Path):
    service = make_service(tmp_path)
    source = tmp_path / "models.xlsx"
    create_source(source)
    stats = service.import_file("shop-123", source)
    assert stats["models"] == 5
    result = service.query_support("shop-123", "Y100", brand_hint="VIVO")
    assert result["status"] == "matched"
    by_material = {item["material_name"]: item["supported"] for item in result["materials"]}
    assert by_material["FL二合一磨砂二代"] is True
    assert by_material["FL液态直边软壳"] is False


def test_longer_model_does_not_match_shorter_model(tmp_path: Path):
    service = make_service(tmp_path)
    source = tmp_path / "models.xlsx"
    create_source(source)
    service.import_file("shop-123", source)
    result = service.query_support("shop-123", "15PRO", brand_hint="苹果")
    assert result["status"] == "matched"
    assert result["model"] == "15PRO"


def test_unknown_query_is_recorded(tmp_path: Path):
    service = make_service(tmp_path)
    source = tmp_path / "models.xlsx"
    create_source(source)
    service.import_file("shop-123", source)
    result = service.query_support("shop-123", "Y999", brand_hint="VIVO", raw_query="vivo y999有吗")
    assert result["status"] == "not_found"


def test_mini_is_not_mistaken_for_xiaomi_mi_prefix():
    parsed = split_model_group("苹果", "苹果13MINI/12MINI通用")
    assert [item.model_name for item in parsed] == ["13MINI", "12MINI"]


def test_vivo_hint_can_match_iqoo_subbrand(tmp_path: Path):
    service = make_service(tmp_path)
    source = tmp_path / "models.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "型号明细"
    ws.append(["材质", "品牌栏目", "型号组合", "库存状态"])
    ws.append(["FL二合一磨砂二代", "VIVO", "IQOO10", "未标注"])
    wb.save(source)
    service.import_file("shop-123", source)
    result = service.query_support("shop-123", "IQOO10", brand_hint="VIVO")
    assert result["status"] == "matched"
