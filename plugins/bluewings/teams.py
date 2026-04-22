# 출처: https://www.kleague.com/record/teamRank.do — data.teamNameList / data.teamNameShortList
# 시즌 팀 구성 변경 시 갱신 필요
K_LEAGUE_2_SHORT_TO_FULL = {
    "부산": "부산 아이파크",
    "수원": "수원 삼성",
    "서울E": "서울 이랜드",
    "수원FC": "수원FC",
    "파주": "파주프런티어FC",
    "김포": "김포FC",
    "대구": "대구FC",
    "충남아산": "충남 아산 FC",
    "천안": "천안시티FC",
    "성남": "성남FC",
    "화성": "화성FC",
    "안산": "안산 그리너스",
    "충북청주": "충북 청주FC",
    "전남": "전남 드래곤즈",
    "경남": "경남FC",
    "용인": "용인FC",
    "김해": "김해FC2008",
}


def short_to_full(short_name: str) -> str:
    if short_name not in K_LEAGUE_2_SHORT_TO_FULL:
        raise KeyError(
            f"K리그2 매핑에 없는 약칭: '{short_name}'. "
            f"plugins/bluewings/teams.py 를 갱신해야 합니다."
        )
    return K_LEAGUE_2_SHORT_TO_FULL[short_name]
