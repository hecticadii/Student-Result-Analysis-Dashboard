import re

import pandas as pd


class ResultEngine:
    GRADE_BINS = [
        ("O", 90),
        ("A++", 85),
        ("A+", 80),
        ("A", 75),
        ("AB", 70),
        ("B+", 65),
        ("B", 60),
        ("C+", 55),
        ("C", 50),
        ("D", 45),
        ("F", 0),
    ]
    GRADE_ORDER = ["O", "A++", "A+", "A", "AB", "B+", "B", "C+", "C", "D", "F"]

    def __init__(self, file_path, sheet_name=0):
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.df = None

        self.roll_col = None
        self.name_col = None
        self.sgpa_col = None
        self.percent_col = None
        self.grade_col = None

        self._result_columns = None
        self._header_row = None
        self._header_main_ffill = None
        self._header_sub = None
        self._invalid_students = pd.DataFrame()
        self._term_by_col = {}
        self._term_columns = {}
        self._term_labels = {}
        self._term_order = {}
        self._term_active_masks = {}
        self._term_sgpa_cols = {}
        self._term_grade_cols = {}
        self._term_percent_cols = {}

    def _reset_source(self):
        if hasattr(self.file_path, "seek"):
            self.file_path.seek(0)

    def _normalize_header_token(self, value):
        return re.sub(r"[^A-Z0-9]", "", str(value).strip().upper())

    def _roman_to_int(self, token):
        mapping = {
            "I": 1,
            "II": 2,
            "III": 3,
            "IV": 4,
            "V": 5,
            "VI": 6,
            "VII": 7,
            "VIII": 8,
            "IX": 9,
            "X": 10,
        }
        return mapping.get(token.upper())

    def _int_to_roman(self, num):
        mapping = {
            1: "I",
            2: "II",
            3: "III",
            4: "IV",
            5: "V",
            6: "VI",
            7: "VII",
            8: "VIII",
            9: "IX",
            10: "X",
        }
        return mapping.get(num, str(num))

    def _extract_term_info(self, value):
        if value is None:
            return None
        txt = str(value).strip()
        if not txt or txt.lower() == "nan":
            return None
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", txt).strip()
        match = re.search(r"\b(term|sem|semester)\b\s+([ivx]+|\d+)", cleaned, re.IGNORECASE)
        if not match:
            return None
        token = match.group(2).strip()
        term_num = None
        if token.isdigit():
            term_num = int(token)
        else:
            term_num = self._roman_to_int(token)
        if not term_num:
            return None
        term_key = f"term_{term_num}"
        display = f"Term {self._int_to_roman(term_num)}"
        return term_key, term_num, display

    def _detect_term_row(self, preview, header_row):
        if preview is None or header_row is None:
            return None
        max_scan = min(80, len(preview))
        best_idx = None
        best_count = 0
        for i in range(max_scan):
            row_vals = preview.iloc[i].fillna("").astype(str)
            count = 0
            for val in row_vals.tolist():
                if self._extract_term_info(val):
                    count += 1
            if count > best_count:
                best_count = count
                best_idx = i
        return best_idx if best_count > 0 else None

    def _detect_result_header_rows(self, preview, header_row):
        if preview is None or header_row is None:
            return header_row, None

        metric_tokens = {
            "INT",
            "EXT",
            "TOT",
            "TOTAL",
            "GR",
            "GRADE",
            "CRPT",
            "CRER",
            "PT",
            "ST",
            "STATUS",
            "PF",
            "RESULT",
            "RES",
        }
        max_scan = min(len(preview), header_row + 4)
        best_idx = None
        best_score = 0

        for i in range(header_row, max_scan):
            row_vals = preview.iloc[i].fillna("").astype(str)
            score = sum(1 for val in row_vals.tolist() if self._normalize_header_token(val) in metric_tokens)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is None or best_score < 4:
            subject_row = header_row
            subheader_row = header_row + 1 if header_row + 1 < len(preview) else None
            return subject_row, subheader_row

        subject_row = best_idx - 1 if best_idx > header_row else header_row
        return subject_row, best_idx

    def _build_term_map(self, term_row):
        if term_row is None or self.df is None:
            return

        term_by_index = []
        current_term = None
        for val in term_row.tolist():
            info = self._extract_term_info(val)
            if info:
                current_term = info
                term_key, order, display = info
                self._term_labels[term_key] = display
                self._term_order[term_key] = order
            term_by_index.append(current_term[0] if current_term else None)

        cols = self.df.columns.tolist()
        for idx, col in enumerate(cols):
            term_key = term_by_index[idx] if idx < len(term_by_index) else None
            if term_key:
                self._term_by_col[col] = term_key
                self._term_columns.setdefault(term_key, []).append(col)

        for col in cols:
            term_key = self._term_by_col.get(col)
            if not term_key:
                continue
            cname = str(col).lower()
            if "sgpa" in cname or re.search(r"\bgpa\b", cname):
                self._term_sgpa_cols.setdefault(term_key, col)
            if re.fullmatch(r"grade(?:\.\d+)?", cname) or cname.endswith("_grade"):
                self._term_grade_cols.setdefault(term_key, col)
            if "percent" in cname or "%" in cname:
                self._term_percent_cols.setdefault(term_key, col)

    def get_terms(self):
        if not self._term_order:
            return []
        ordered = sorted(self._term_order.items(), key=lambda item: item[1])
        return [term_key for term_key, _ in ordered]

    def _use_single_term_global_fallback(self, term_key):
        if not term_key:
            return False
        terms = self.get_terms()
        return len(terms) == 1 and terms[0] == term_key

    def get_term_label(self, term_key):
        return self._term_labels.get(term_key, term_key)

    def get_term_columns(self, term_key):
        cols = list(self._term_columns.get(term_key, []))
        if cols:
            return cols
        if self._use_single_term_global_fallback(term_key) and self.df is not None:
            return list(self.df.columns)
        return cols

    def get_term_sgpa_col(self, term_key):
        col = self._term_sgpa_cols.get(term_key)
        if col:
            return col
        if self._use_single_term_global_fallback(term_key):
            return self.sgpa_col
        return None

    def get_term_grade_col(self, term_key):
        col = self._term_grade_cols.get(term_key)
        if col:
            return col
        if self._use_single_term_global_fallback(term_key):
            return self.grade_col
        return None

    def get_term_result_columns(self, term_key):
        result_cols = self._detect_result_columns()
        if not term_key:
            return result_cols
        filtered = [item for item in result_cols if self._term_by_col.get(item["column"]) == term_key]
        if filtered:
            return filtered
        if self._use_single_term_global_fallback(term_key):
            return result_cols
        return filtered

    def get_term_active_mask(self, term_key):
        if not term_key:
            return pd.Series(True, index=self.df.index)
        if term_key in self._term_active_masks:
            return self._term_active_masks[term_key]
        result_cols = self.get_term_result_columns(term_key)
        cols = []
        for item in result_cols:
            cols.extend(self._get_item_status_columns(item))
            cols.extend(self._get_item_marks_columns(item))
        extra_cols = [
            self.get_term_sgpa_col(term_key),
            self.get_term_grade_col(term_key),
        ]
        cols = [c for c in cols + extra_cols if c and c in self.df.columns]
        if not cols:
            cols = self.get_term_columns(term_key)
        if not cols:
            mask = pd.Series(True, index=self.df.index)
            self._term_active_masks[term_key] = mask
            return mask
        term_df = self.df[cols]
        blank_mask = term_df.apply(lambda col: col.map(self._is_blank_value)).all(axis=1)
        active_mask = ~blank_mask
        self._term_active_masks[term_key] = active_mask
        return active_mask

    def _detect_important_columns(self):
        for col in self.df.columns:
            c = col.lower()

            if self.roll_col is None and ("roll" in c or "prn" in c):
                self.roll_col = col

            if self.name_col is None and "name" in c:
                self.name_col = col

            if self.sgpa_col is None and ("sgpa" in c or "gpa" in c):
                self.sgpa_col = col

            if self.percent_col is None and ("percent" in c or "%" in c):
                self.percent_col = col

            if self.grade_col is None and (re.fullmatch(r"grade(?:\.\d+)?", c) or c.endswith("_grade")):
                self.grade_col = col

        if self.sgpa_col is None:
            for fallback in ["sem_5.2", "sem_6.2", "sem_5", "sem_6"]:
                if fallback in self.df.columns:
                    self.sgpa_col = fallback
                    break

        if self.grade_col is None:
            for fallback in ["sem_5.4", "sem_6.4", "sem_5_grade", "sem_6_grade", "grade"]:
                if fallback in self.df.columns:
                    self.grade_col = fallback
                    break

    def _parse_subject_and_code(self, raw_label):
        txt = str(raw_label).strip()
        match = re.match(r"^(.*?)\(\s*([^)]+)\s*\)\s*$", txt)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        return txt, ""

    def _subject_key(self, subject_name, course_code):
        if course_code:
            return f"{subject_name} ({course_code})"
        return subject_name

    def _is_generic_or_empty_label(self, label):
        txt = str(label).strip().lower()
        if txt in {"", "nan", "none", "-", "_"}:
            return True
        if txt.startswith("unnamed:") or txt.startswith("unnamed_"):
            return True

        generic_tokens = [
            "roll",
            "prn",
            "student",
            "name",
            "sem",
            "term",
            "credit",
            "grade",
            "total",
            "result",
            "status",
            "sgpa",
            "cgpa",
            "gpa",
            "percentage",
            "percent",
            "sr_no",
            "sr no",
            "srno",
            "sr.no",
            "int",
            "ext",
            "tot",
            "p/f",
            "pf",
        ]
        return any(token in txt for token in generic_tokens)

    def _looks_like_subject(self, label):
        txt = str(label).strip()
        if not txt:
            return False
        if self._is_generic_or_empty_label(txt):
            return False
        if "(" in txt and ")" in txt:
            return True
        if re.search(r"\b[A-Z]{2,}\d{2,}\b", txt):
            return True
        if re.search(r"\bOEL-\d+\b", txt, re.IGNORECASE):
            return True
        return False

    def _is_blank_value(self, value):
        if pd.isna(value):
            return True
        txt = str(value).strip().lower()
        return txt in {"", "-", "nan", "na", "none", "null"}

    def _find_blank_subject_rows(self):
        result_cols = self._detect_result_columns()
        if not result_cols:
            return pd.DataFrame(columns=["PRN No", "Student Name"]), pd.Series(dtype=bool)

        check_cols = []
        pf_cols = []
        marks_cols = []
        for item in result_cols:
            for col in self._get_item_status_columns(item):
                if col in self.df.columns:
                    check_cols.append(col)
                    pf_cols.append(col)
            for marks_col in self._get_item_marks_columns(item):
                if marks_col in self.df.columns:
                    check_cols.append(marks_col)
                    marks_cols.append(marks_col)

        if self.sgpa_col and self.sgpa_col in self.df.columns:
            check_cols.append(self.sgpa_col)
        if self.grade_col and self.grade_col in self.df.columns:
            check_cols.append(self.grade_col)
        if self.percent_col and self.percent_col in self.df.columns:
            check_cols.append(self.percent_col)

        if not check_cols:
            return pd.DataFrame(columns=["PRN No", "Student Name"]), pd.Series(dtype=bool)

        blank_mask = self.df[check_cols].apply(lambda col: col.map(self._is_blank_value)).all(axis=1)

        # If all marks are blank and results are only fail/absent (no pass), treat as invalid.
        marks_blank = pd.Series(False, index=self.df.index)
        if marks_cols:
            marks_only = self.df[marks_cols].apply(pd.to_numeric, errors="coerce")
            marks_blank = marks_only.isna().all(axis=1)

        results_bad_all = pd.Series(False, index=self.df.index)
        if pf_cols:
            res = self.df[pf_cols].astype(str).apply(lambda col: col.str.strip().str.upper())
            bad_set = {"", "-", "NAN", "NA", "NONE", "NULL", "F", "FAIL", "AB", "ABSENT"}
            results_bad_all = res.isin(bad_set).all(axis=1)

        sgpa_blank = pd.Series(True, index=self.df.index)
        if self.sgpa_col and self.sgpa_col in self.df.columns:
            sgpa = pd.to_numeric(self.df[self.sgpa_col], errors="coerce")
            sgpa_blank = sgpa.isna() | (sgpa <= 0)

        blank_mask = blank_mask | (marks_blank & results_bad_all & sgpa_blank)
        # Fallback: if marks/results are missing but the row has no numeric values at all, treat as blank.
        numeric_cols = self.df.columns.difference([self.roll_col, self.name_col])
        if not numeric_cols.empty:
            numeric_values = self.df[numeric_cols].apply(pd.to_numeric, errors="coerce")
            blank_mask = blank_mask | numeric_values.notna().sum(axis=1).eq(0)
        invalid = self.df.loc[blank_mask, [self.roll_col, self.name_col]].copy()
        invalid.rename(columns={self.roll_col: "PRN No", self.name_col: "Student Name"}, inplace=True)
        return invalid.reset_index(drop=True), blank_mask

    def _resolve_subject_label(self, idx):
        # Prefer meaningful labels from the original header row.
        if self._header_main_ffill is not None:
            for j in range(idx, -1, -1):
                raw = self._header_main_ffill.iloc[j]
                if not self._is_generic_or_empty_label(raw):
                    return str(raw).strip()

        # Fallback to cleaned dataframe column labels.
        cols = self.df.columns.tolist()
        for j in range(idx, -1, -1):
            raw = cols[j]
            if not self._is_generic_or_empty_label(raw):
                return str(raw).strip()

        return f"subject_{idx + 1}"

    def _detect_header_row(self, preview):
        candidates = []
        max_scan = min(40, len(preview))

        for i in range(max_scan):
            row_vals = preview.iloc[i].fillna("").astype(str).str.strip()
            row_lower = [str(x).strip().lower() for x in row_vals.tolist()]

            has_roll = any("roll" in x or "prn" in x for x in row_lower)
            has_name = any("name" in x or "student" in x for x in row_lower)
            if not (has_roll and has_name):
                continue

            non_empty = int((row_vals.str.lower() != "nan").sum())
            subject_like = int(
                row_vals.str.contains(r"\(|-th|-pr|subject|course", case=False, regex=True, na=False).sum()
            )
            score = (non_empty * 2) + (subject_like * 5)
            candidates.append((score, i))

        if not candidates:
            return 0

        candidates.sort(reverse=True)
        return candidates[0][1]

    def _build_result_columns_from_headers(self):
        result_cols = []
        if self._header_sub is None or self._header_main_ffill is None:
            return result_cols

        cols = self.df.columns.tolist()
        for idx, col in enumerate(cols):
            sub = self._normalize_header_token(self._header_sub.iloc[idx])
            if sub not in {"PF", "RESULT", "RES", "ST", "STATUS"}:
                continue

            main_raw = self._resolve_subject_label(idx)
            if not self._looks_like_subject(main_raw):
                continue
            subject_name, course_code = self._parse_subject_and_code(main_raw)

            marks_col = None
            left_bound = max(0, idx - 8)
            for j in range(idx - 1, left_bound - 1, -1):
                sub_j = self._normalize_header_token(self._header_sub.iloc[j])
                if sub_j in {"TOT", "TOTAL"}:
                    marks_col = cols[j]
                    break

            # Fallback marks column if no explicit TOT in sub-header row.
            if marks_col is None:
                marks_col = cols[idx - 1] if idx > 0 else None

            result_cols.append(self._make_result_item(col, subject_name, course_code, marks_col))
        return result_cols

    def _build_result_columns_from_values(self):
        result_cols = []
        cols = self.df.columns.tolist()

        for idx, col in enumerate(cols):
            s = self.df[col].dropna().astype(str).str.strip().str.upper()
            if s.empty:
                continue

            valid = {"P", "F", "PASS", "FAIL", "AB", "ABSENT"}
            values = set(s.unique().tolist())
            if values.issubset(valid) and (
                "P" in values or "F" in values or "PASS" in values or "FAIL" in values
            ):
                raw_name = self._resolve_subject_label(idx)
                if not self._looks_like_subject(raw_name):
                    continue
                subject_name, course_code = self._parse_subject_and_code(raw_name)
                result_cols.append(
                    self._make_result_item(col, subject_name, course_code, cols[idx - 1] if idx > 0 else None)
                )

        return result_cols

    def _detect_result_columns(self):
        if self._result_columns is not None:
            return self._result_columns

        result_cols = self._build_result_columns_from_headers()
        if not result_cols:
            result_cols = self._build_result_columns_from_values()

        result_cols = self._merge_result_columns(result_cols)

        self._result_columns = result_cols
        return result_cols

    def _make_result_item(self, col, subject_name, course_code, marks_col=None):
        return {
            "column": col,
            "subject_name": subject_name,
            "course_code": course_code,
            "subject_key": self._subject_key(subject_name, course_code),
            "marks_column": marks_col,
            "candidates": [{"column": col, "marks_column": marks_col}],
        }

    def _merge_result_columns(self, result_cols):
        merged = {}
        ordered = []

        for item in result_cols:
            term_key = self._term_by_col.get(item["column"])
            group_key = (term_key, item["subject_key"])
            candidate_items = item.get("candidates") or [
                {"column": item["column"], "marks_column": item.get("marks_column")}
            ]

            if group_key not in merged:
                merged_item = dict(item)
                merged_item["term_key"] = term_key
                merged_item["candidates"] = [dict(candidate) for candidate in candidate_items]
                merged[group_key] = merged_item
                ordered.append(merged_item)
                continue

            existing = merged[group_key]
            seen_pairs = {
                (candidate.get("column"), candidate.get("marks_column")) for candidate in existing["candidates"]
            }
            for candidate in candidate_items:
                pair = (candidate.get("column"), candidate.get("marks_column"))
                if pair in seen_pairs:
                    continue
                existing["candidates"].append(dict(candidate))
                seen_pairs.add(pair)

        for item in ordered:
            candidates = item.get("candidates", [])
            if candidates:
                item["column"] = candidates[0].get("column")
                item["marks_column"] = candidates[0].get("marks_column")

        return ordered

    def _get_item_candidates(self, item):
        candidates = item.get("candidates") or [{"column": item["column"], "marks_column": item.get("marks_column")}]
        cleaned = []
        seen = set()
        for candidate in candidates:
            col = candidate.get("column")
            marks_col = candidate.get("marks_column")
            if not col or col not in self.df.columns:
                continue
            pair = (col, marks_col)
            if pair in seen:
                continue
            cleaned.append({"column": col, "marks_column": marks_col})
            seen.add(pair)
        return cleaned

    def _get_item_status_columns(self, item):
        return [candidate["column"] for candidate in self._get_item_candidates(item)]

    def _get_item_marks_columns(self, item):
        cols = []
        for candidate in self._get_item_candidates(item):
            marks_col = candidate.get("marks_column")
            if marks_col and marks_col in self.df.columns and marks_col not in cols:
                cols.append(marks_col)
        return cols

    def _normalize_result_value(self, value):
        if self._is_blank_value(value):
            return ""
        txt = str(value).strip().upper()
        if txt in {"P", "PASS"}:
            return "PASS"
        if txt in {"F", "FAIL"}:
            return "FAIL"
        if txt in {"AB", "ABSENT"}:
            return "ABSENT"
        return txt

    def _resolve_item_series(self, df, item):
        result_series = pd.Series("", index=df.index, dtype=object)
        marks_series = pd.Series(index=df.index, dtype=float)

        for candidate in self._get_item_candidates(item):
            status_col = candidate["column"]
            status_values = df[status_col].fillna("").astype(str).str.strip()
            valid_status = ~status_values.map(self._is_blank_value)
            result_series.loc[valid_status] = status_values.loc[valid_status]

            marks_col = candidate.get("marks_column")
            if marks_col and marks_col in df.columns:
                marks_values = pd.to_numeric(df[marks_col], errors="coerce")
                valid_marks = marks_values.notna()
                marks_series.loc[valid_marks] = marks_values.loc[valid_marks]

        return result_series, pd.to_numeric(marks_series, errors="coerce")

    def _resolve_item_row_values(self, row, item):
        result_val = ""
        marks_val = None

        for candidate in self._get_item_candidates(item):
            status_col = candidate["column"]
            raw_result = row.get(status_col)
            if not self._is_blank_value(raw_result):
                result_val = str(raw_result).strip()

            marks_col = candidate.get("marks_column")
            if marks_col and marks_col in row.index:
                marks_raw = pd.to_numeric(pd.Series([row[marks_col]]), errors="coerce").iloc[0]
                if pd.notna(marks_raw):
                    marks_val = float(marks_raw)

        return result_val, marks_val

    def _sgpa_to_grade(self, sgpa):
        if pd.isna(sgpa):
            return "-"
        if sgpa >= 9.0:
            return "O"
        if sgpa >= 8.0:
            return "A+"
        if sgpa >= 7.0:
            return "A"
        if sgpa >= 6.0:
            return "B+"
        if sgpa >= 5.0:
            return "B"
        if sgpa >= 4.0:
            return "C"
        return "F"

    def _grade_from_percent(self, percent):
        for label, cutoff in self.GRADE_BINS:
            if percent >= cutoff:
                return label
        return "F"

    def _infer_marks_scale(self, marks_series):
        if marks_series is None or marks_series.empty:
            return 100
        max_mark = pd.to_numeric(marks_series, errors="coerce").max()
        if pd.isna(max_mark):
            return 100
        if max_mark <= 50:
            return 50
        if max_mark <= 75:
            return 75
        if max_mark <= 80:
            return 80
        return 100

    def load_data(self):
        self._reset_source()
        preview = pd.read_excel(self.file_path, header=None, sheet_name=self.sheet_name, nrows=60)

        header_row = self._detect_header_row(preview)
        term_row = self._detect_term_row(preview, header_row)
        subject_row, subheader_row = self._detect_result_header_rows(preview, header_row)

        self._header_row = header_row
        self._header_main_ffill = preview.iloc[subject_row].ffill()
        self._header_sub = preview.iloc[subheader_row] if subheader_row is not None and subheader_row < len(preview) else None

        self._reset_source()
        self.df = pd.read_excel(self.file_path, header=header_row, sheet_name=self.sheet_name)
        self.df.columns = (
            self.df.columns.astype(str).str.strip().str.lower().str.replace(" ", "_")
        )

        if term_row is not None and term_row < len(preview):
            self._build_term_map(preview.iloc[term_row])

        print("Detected columns:", self.df.columns.tolist())

        self._detect_important_columns()

        print("Roll column:", self.roll_col)
        print("Name column:", self.name_col)
        print("SGPA column:", self.sgpa_col)

        if self.roll_col is None:
            raise ValueError("Roll/PRN column not found")
        if self.name_col is None:
            raise ValueError("Student name column not found")
        if self.sgpa_col is None:
            raise ValueError("SGPA column not found")

        self.df = self.df.dropna(how="all")
        self.df = self.df[self.df[self.roll_col].notna()]
        self.df = self.df[self.df[self.roll_col].astype(str).str.contains(r"\d", na=False)]
        self.df = self.df.reset_index(drop=True)

        print("Filtered students:", len(self.df))

        self.df[self.roll_col] = (
            self.df[self.roll_col].astype(str).str.replace(".0", "", regex=False)
        )
        self.df[self.name_col] = self.df[self.name_col].astype(str).str.strip()
        self.df[self.sgpa_col] = pd.to_numeric(self.df[self.sgpa_col], errors="coerce")

        self.df = self.df[self.df[self.roll_col].notna()].reset_index(drop=True)

        self._invalid_students, blank_mask = self._find_blank_subject_rows()
        if not self._invalid_students.empty and not blank_mask.empty:
            self.df = self.df.loc[~blank_mask].reset_index(drop=True)

        print("Students loaded:", len(self.df))

    def get_class_overview(self, term_key=None):
        df = self.df
        result_cols = self._detect_result_columns()
        sgpa_col = self.sgpa_col

        if term_key:
            result_cols = self.get_term_result_columns(term_key)
            df = df.loc[self.get_term_active_mask(term_key)]
            sgpa_col = self.get_term_sgpa_col(term_key)

        total_students = len(df)
        if result_cols:
            failed = 0
            for _, row in df.iterrows():
                has_fail = any(
                    self._normalize_result_value(self._resolve_item_row_values(row, item)[0]) in {"FAIL", "ABSENT"}
                    for item in result_cols
                )
                if has_fail:
                    failed += 1
            passed = total_students - failed
        elif sgpa_col and sgpa_col in df.columns:
            sgpa = pd.to_numeric(df[sgpa_col], errors="coerce")
            passed = int((sgpa >= 4).sum())
            failed = total_students - passed
        else:
            passed = 0
            failed = 0

        if sgpa_col and sgpa_col in df.columns and total_students:
            average_sgpa = float(round(pd.to_numeric(df[sgpa_col], errors="coerce").mean(), 2))
        else:
            average_sgpa = 0.0

        pass_percent = round((passed / total_students) * 100, 2) if total_students else 0.0

        return {
            "total_students": total_students,
            "passed": passed,
            "failed": failed,
            "average_sgpa": average_sgpa,
            "pass_percent": pass_percent,
        }

    def get_class_toppers(self, n=3, term_key=None):
        df = self.df
        sgpa_col = self.sgpa_col
        grade_col = self.grade_col

        if term_key:
            df = df.loc[self.get_term_active_mask(term_key)]
            sgpa_col = self.get_term_sgpa_col(term_key)
            grade_col = self.get_term_grade_col(term_key)

        if not sgpa_col or sgpa_col not in df.columns or df.empty:
            return pd.DataFrame(columns=[self.name_col, self.roll_col, sgpa_col or "sgpa", "grade"])

        sorted_df = df.sort_values(by=sgpa_col, ascending=False)
        top_df = sorted_df.head(n)

        top_df = top_df[[self.name_col, self.roll_col, sgpa_col]].copy()
        if grade_col and grade_col in df.columns:
            top_df["grade"] = df.loc[top_df.index, grade_col].astype(str).str.strip()
        else:
            top_df["grade"] = top_df[sgpa_col].apply(self._sgpa_to_grade)

        return top_df.reset_index(drop=True)

    def get_class_grade_summary(self, term_key=None):
        overview = self.get_class_overview(term_key)
        df = self.df
        sgpa_col = self.sgpa_col
        if term_key:
            df = df.loc[self.get_term_active_mask(term_key)]
            sgpa_col = self.get_term_sgpa_col(term_key)
        if sgpa_col and sgpa_col in df.columns:
            sgpa = pd.to_numeric(df[sgpa_col], errors="coerce")
        else:
            sgpa = pd.Series(dtype=float)

        distinction = int((sgpa >= 8).sum()) if not sgpa.empty else 0
        first_class = int(((sgpa >= 6.5) & (sgpa < 8)).sum()) if not sgpa.empty else 0
        second_class = int(((sgpa >= 4) & (sgpa < 6.5)).sum()) if not sgpa.empty else 0
        overall_failed = int((sgpa < 4).sum()) if not sgpa.empty else 0

        total_students = int(overview.get("total_students", 0))
        passed = int(overview.get("passed", 0))
        atkt = int(overview.get("failed", 0))
        pass_with_atkt = round(((passed + atkt) / total_students) * 100, 2) if total_students else 0.0

        return {
            "total_students": total_students,
            "passed": passed,
            "failed": int(overview.get("failed", 0)),
            "pass_percent": float(overview.get("pass_percent", 0.0)),
            "pass_with_atkt": pass_with_atkt,
            "distinction": distinction,
            "first_class": first_class,
            "second_class": second_class,
            "overall_failed": overall_failed,
        }

    def get_subject_analysis(self, term_key=None):
        data = []
        result_cols = self._detect_result_columns()
        df = self.df
        if term_key:
            result_cols = self.get_term_result_columns(term_key)
            df = df.loc[self.get_term_active_mask(term_key)]

        for i, item in enumerate(result_cols, start=1):
            subject_name = item["subject_name"]
            course_code = item["course_code"]
            if self._is_generic_or_empty_label(subject_name):
                subject_name = f"Subject {i}"
            if self._is_generic_or_empty_label(course_code):
                course_code = ""
            subject_key = self._subject_key(subject_name, course_code)
            s, marks = self._resolve_item_series(df, item)
            s = s.map(self._normalize_result_value)
            eval_mask = s.isin(["PASS", "FAIL", "ABSENT"])

            passed = int((s == "PASS").sum())
            failed = int((s == "FAIL").sum() + (s == "ABSENT").sum())
            appeared = int(eval_mask.sum())

            if appeared == 0:
                continue

            pass_percent = round((passed / appeared) * 100, 2)

            topper_name = "-"
            topper_prn = "-"
            topper_marks = None
            top_mask = eval_mask & marks.notna()
            if top_mask.any():
                top_idx = marks[top_mask].idxmax()
                topper_name = str(df.loc[top_idx, self.name_col])
                topper_prn = str(df.loc[top_idx, self.roll_col])
                topper_marks = float(marks.loc[top_idx])

            data.append(
                {
                    "subject_name": subject_name,
                    "course_code": course_code,
                    "subject": subject_key,
                    "appeared": appeared,
                    "passed": passed,
                    "failed": failed,
                    "pass_percent": pass_percent,
                    "topper_name": topper_name,
                    "topper_prn": topper_prn,
                    "topper_marks": topper_marks,
                }
            )

        if not data:
            return pd.DataFrame(
                columns=[
                    "subject_name",
                    "course_code",
                    "subject",
                    "appeared",
                    "passed",
                    "failed",
                    "pass_percent",
                    "topper_name",
                    "topper_prn",
                    "topper_marks",
                ]
            )

        return pd.DataFrame(data).sort_values("pass_percent", ascending=False).reset_index(drop=True)

    def get_subject_grade_distribution(self, term_key=None):
        rows = []
        result_cols = self._detect_result_columns()
        df = self.df
        if term_key:
            result_cols = self.get_term_result_columns(term_key)
            df = df.loc[self.get_term_active_mask(term_key)]
        total_students = len(df)

        for i, item in enumerate(result_cols, start=1):
            subject_name = item["subject_name"]
            course_code = item["course_code"]
            if self._is_generic_or_empty_label(subject_name):
                subject_name = f"Subject {i}"
            if self._is_generic_or_empty_label(course_code):
                course_code = ""
            subject_key = self._subject_key(subject_name, course_code)

            s, marks = self._resolve_item_series(df, item)
            s = s.map(self._normalize_result_value)
            passed_mask = s == "PASS"
            failed_mask = s == "FAIL"
            absent_mask = s == "ABSENT"

            appeared = int((passed_mask | failed_mask).sum())
            passed = int(passed_mask.sum())
            failed = int(failed_mask.sum())
            not_appeared = int(absent_mask.sum())

            grade_counts = {label: 0 for label in self.GRADE_ORDER}

            scale = self._infer_marks_scale(marks)
            for mark in marks[passed_mask]:
                if pd.isna(mark):
                    continue
                percent = (float(mark) / scale) * 100 if scale else 0.0
                grade = self._grade_from_percent(percent)
                grade_counts[grade] += 1

            grade_counts["F"] += failed

            pass_percent = round((passed / appeared) * 100, 2) if appeared else None

            row = {
                "subject": subject_key,
                "subject_name": subject_name,
                "course_code": course_code,
                "faculty": "",
                "total": total_students,
                "appeared": appeared,
                "passed": passed,
                "failed": failed,
                "not_appeared": not_appeared,
                "before_remedial_result": pass_percent,
            }
            for grade_label in self.GRADE_ORDER:
                row[grade_label] = int(grade_counts.get(grade_label, 0))

            rows.append(row)

        if not rows:
            cols = [
                "subject",
                "subject_name",
                "course_code",
                "faculty",
                "total",
                "appeared",
                "passed",
                "failed",
                "not_appeared",
                "before_remedial_result",
            ] + self.GRADE_ORDER
            return pd.DataFrame(columns=cols)

        df = pd.DataFrame(rows)
        ordered_cols = [
            "subject",
            "faculty",
            "O",
            "A++",
            "A+",
            "A",
            "AB",
            "B+",
            "B",
            "C+",
            "C",
            "D",
            "F",
            "total",
            "appeared",
            "passed",
            "failed",
            "not_appeared",
            "before_remedial_result",
        ]
        ordered_cols = [c for c in ordered_cols if c in df.columns]
        return df[ordered_cols].copy()

    def get_subject_summary(self):
        df = self.get_subject_analysis()
        if df.empty:
            return {}

        summary = {}
        for _, row in df.iterrows():
            summary[row["subject"]] = {
                "appeared": int(row["appeared"]),
                "passed": int(row["passed"]),
                "failed": int(row["failed"]),
                "pass_percent": float(row["pass_percent"]),
                "topper_name": row["topper_name"],
                "topper_prn": row["topper_prn"],
                "topper_marks": row["topper_marks"],
            }
        return summary

    def get_result_columns(self, term_key=None):
        if term_key:
            return list(self.get_term_result_columns(term_key))
        return list(self._detect_result_columns())

    def get_student_subject_report(self, roll_no, term_key=None):
        result_cols = self._detect_result_columns()
        if term_key:
            result_cols = self.get_term_result_columns(term_key)
        student = self.df[self.df[self.roll_col].astype(str) == str(roll_no)]

        if student.empty or not result_cols:
            return pd.DataFrame(
                columns=[
                    "subject_name",
                    "course_code",
                    "subject",
                    "result",
                    "marks",
                ]
            )

        row = student.iloc[0]
        rows = []
        for i, item in enumerate(result_cols, start=1):
            subject_name = item["subject_name"]
            course_code = item["course_code"]
            if self._is_generic_or_empty_label(subject_name):
                subject_name = f"Subject {i}"
            if self._is_generic_or_empty_label(course_code):
                course_code = ""
            subject_key = self._subject_key(subject_name, course_code)

            result_val, marks_val = self._resolve_item_row_values(row, item)
            result_val = self._normalize_result_value(result_val)
            if not result_val:
                result_val = "-"

            rows.append(
                {
                    "subject_name": subject_name,
                    "course_code": course_code,
                    "subject": subject_key,
                    "result": result_val,
                    "marks": marks_val,
                }
            )

        return pd.DataFrame(rows)

    def get_invalid_students(self):
        if self._invalid_students is None:
            return pd.DataFrame(columns=["PRN No", "Student Name"])
        return self._invalid_students.copy()

    def get_student_matrix(self, term_key=None):
        matrix = {}
        result_cols = self._detect_result_columns()
        df = self.df
        sgpa_col = self.sgpa_col
        if term_key:
            result_cols = self.get_term_result_columns(term_key)
            df = df.loc[self.get_term_active_mask(term_key)]
            sgpa_col = self.get_term_sgpa_col(term_key)

        for _, row in df.iterrows():
            roll = row[self.roll_col]
            name = row[self.name_col]
            failed_subjects = []

            for i, item in enumerate(result_cols, start=1):
                subject_name = item["subject_name"]
                course_code = item["course_code"]
                if self._is_generic_or_empty_label(subject_name):
                    subject_name = f"Subject {i}"
                if self._is_generic_or_empty_label(course_code):
                    course_code = ""
                subject_key = self._subject_key(subject_name, course_code)

                val = self._normalize_result_value(self._resolve_item_row_values(row, item)[0])
                if val in {"FAIL", "ABSENT"}:
                    failed_subjects.append(subject_key)

            if (
                not result_cols
                and sgpa_col
                and sgpa_col in df.columns
                and pd.notna(row[sgpa_col])
                and float(row[sgpa_col]) < 4
            ):
                failed_subjects.append("Overall (SGPA below passing)")

            matrix[roll] = {
                "name": name,
                "passed_all": len(failed_subjects) == 0,
                "failed_subjects": failed_subjects,
            }

        return matrix
