from parser import normalize_parse_result

result = {
    "questions": [
        {
            "question_num": 14,
            "q_type": "选择题",
            "stem": "已知Cr(OH)3为两性氢氧化物，常温下，在不同pH条件下，... [图片9]",
            "options": [
                "A 由M点可以计算Ksp",
                "B Cr3+恰好完全沉淀的pH=6.7",
                "C P点溶液质量小于Q点溶液质量",
                "D 随着pH的增大"
            ]
        }
    ]
}

# Image count = 10 so 9 is valid
normalized = normalize_parse_result(result, image_count=10, allowed_question_nums={14})

print("Normalized image_refs:", normalized["questions"][0].get("image_refs"))
