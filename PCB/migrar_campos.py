#!/usr/bin/env python3
"""
migrar_campos.py - passa os valores de campos antigos (ex.: "Ref") para os
campos novos (MPN, Distributor, Distributor_PN) nos ficheiros .kicad_sch e
apaga os campos antigos.

Edita o texto diretamente (sem reescrever o ficheiro todo), por isso a
formatação e tudo o resto do esquemático ficam intactos.

Uso:
  python3 migrar_campos.py /caminho/do/projeto            # só mostra o que faria
  python3 migrar_campos.py /caminho/do/projeto --apply    # aplica (cria .bak)
  python3 migrar_campos.py folha1.kicad_sch folha2.kicad_sch --apply

IMPORTANTE: fecha o esquemático no KiCad antes de usar --apply.
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Campo antigo -> campo novo. Descomenta as linhas que quiseres migrar também.
# ---------------------------------------------------------------------------
MAPPING = {
    "Ref": "MPN",
    "Ref_Mouser": "MPN",                    # no teu projeto contém MPNs
    "Manufacturer_Part_Number": "MPN",
    "MP": "MPN",
    "Mouser Part Number": "Distributor_PN",
    "Distribuidor": "Distributor",
    "Destribuidor": "Distributor",
    # Field4..Field8 NÃO: foram copiados de outros componentes e estão errados
}

# Campo usado no relatório final de componentes sem part number
CHECK_FIELD = "MPN"


# --------------------------- parser S-expression ---------------------------
class Node:
    __slots__ = ("start", "end", "items")

    def __init__(self, start):
        self.start, self.end, self.items = start, None, []


def tokenize(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            yield c, i, i + 1
            i += 1
        elif c == '"':
            j = i + 1
            while j < n:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == '"':
                    break
                j += 1
            yield "str", i, j + 1
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()"':
                j += 1
            yield "atom", i, j
            i = j


def parse(s):
    stack, root = [], None
    for kind, a, b in tokenize(s):
        if kind == "(":
            node = Node(a)
            if stack:
                stack[-1].items.append(node)
            stack.append(node)
        elif kind == ")":
            if not stack:
                raise ValueError(f"parêntese ')' a mais na posição {a}")
            node = stack.pop()
            node.end = b
            if not stack:
                root = node
        else:
            if not stack:
                raise ValueError("texto fora de qualquer lista")
            stack[-1].items.append((kind, a, b))
    if stack:
        raise ValueError("parênteses por fechar")
    return root


def raw(s, tok):
    return s[tok[1]:tok[2]]


def unquote(t):
    if t.startswith('"') and t.endswith('"'):
        t = t[1:-1]
    out, i = [], 0
    while i < len(t):
        if t[i] == "\\" and i + 1 < len(t):
            out.append({"n": "\n", "t": "\t"}.get(t[i + 1], t[i + 1]))
            i += 2
        else:
            out.append(t[i])
            i += 1
    return "".join(out)


def quote(v):
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def head(s, node):
    if node.items and isinstance(node.items[0], tuple):
        return raw(s, node.items[0])
    return None


# ------------------------------ lógica ------------------------------------
def symbol_props(s, sym):
    props = {}
    for it in sym.items:
        if isinstance(it, Node) and head(s, it) == "property" and len(it.items) >= 3:
            name_tok, val_tok = it.items[1], it.items[2]
            if isinstance(name_tok, tuple) and isinstance(val_tok, tuple):
                props[unquote(raw(s, name_tok))] = {
                    "node": it, "name_tok": name_tok, "val_tok": val_tok,
                    "val": unquote(raw(s, val_tok)), "raw": raw(s, val_tok),
                }
    return props


def in_bom(s, sym):
    for it in sym.items:
        if isinstance(it, Node) and head(s, it) == "in_bom" and len(it.items) > 1:
            return raw(s, it.items[1]) != "no"
    return True


def delete_span(s, node):
    """Apaga a lista inteira, incluindo a indentação e a quebra de linha."""
    a, b = node.start, node.end
    while a > 0 and s[a - 1] in " \t":
        a -= 1
    if a > 0 and s[a - 1] == "\n":
        a -= 1
        if a > 0 and s[a - 1] == "\r":
            a -= 1
    return a, b, ""


def process(text, mapping):
    root = parse(text)
    if root is None or head(text, root) != "kicad_sch":
        raise ValueError("não parece um ficheiro .kicad_sch")

    edits, log, conflicts, missing = [], [], [], []

    # só os símbolos colocados (filhos diretos da raiz); ignora lib_symbols
    for sym in (n for n in root.items if isinstance(n, Node) and head(text, n) == "symbol"):
        props = symbol_props(text, sym)
        ref = props.get("Reference", {}).get("val", "?")
        lib = ""
        for it in sym.items:
            if isinstance(it, Node) and head(text, it) == "lib_id":
                lib = unquote(raw(text, it.items[1]))
        if lib.startswith("power:"):
            continue

        targets = {k: dict(v) for k, v in props.items()}  # estado atual dos campos
        for src, dst in mapping.items():
            if src not in props or src == dst:
                continue
            p = props[src]
            sval = p["val"].strip()

            if not sval:
                edits.append(delete_span(text, p["node"]))
                log.append(f"  {ref:8} '{src}' vazio -> apagado")
                continue

            if dst in targets:
                d = targets[dst]
                dval = d["val"].strip()
                if not dval:
                    if "val_tok" in d:  # campo destino já existe no ficheiro
                        edits.append((d["val_tok"][1], d["val_tok"][2], p["raw"]))
                    d["val"] = p["val"]
                    edits.append(delete_span(text, p["node"]))
                    log.append(f"  {ref:8} {src} -> {dst} = {sval}")
                elif dval == sval:
                    edits.append(delete_span(text, p["node"]))
                    log.append(f"  {ref:8} '{src}' igual a '{dst}' -> apagado")
                else:
                    conflicts.append(f"  {ref:8} {src}='{sval}' mas {dst}='{dval}' (mantido, decide à mão)")
            else:
                # o campo destino não existe: renomeia (mantém posição e visibilidade)
                edits.append((p["name_tok"][1], p["name_tok"][2], quote(dst)))
                targets[dst] = {"val": p["val"]}
                log.append(f"  {ref:8} {src} renomeado para {dst} = {sval}")

        if in_bom(text, sym) and not targets.get(CHECK_FIELD, {}).get("val", "").strip():
            missing.append(f"{ref} ({lib})")

    # aplica de trás para a frente para não estragar as posições
    edits.sort(key=lambda e: e[0], reverse=True)
    last = len(text) + 1
    out = text
    for a, b, new in edits:
        if b > last:
            raise RuntimeError("edições sobrepostas - nada foi alterado")
        out = out[:a] + new + out[b:]
        last = a

    parse(out)  # valida que o resultado continua bem formado
    return out, log, conflicts, missing, len(edits)


def main():
    ap = argparse.ArgumentParser(description="Migra campos antigos para os novos em .kicad_sch")
    ap.add_argument("paths", nargs="+", help="pasta do projeto ou ficheiros .kicad_sch")
    ap.add_argument("--apply", action="store_true", help="grava as alterações (por omissão só mostra)")
    args = ap.parse_args()

    files = []
    for p in map(Path, args.paths):
        files += sorted(p.rglob("*.kicad_sch")) if p.is_dir() else [p]
    files = [f for f in files if "-backups" not in str(f)]
    if not files:
        sys.exit("Nenhum .kicad_sch encontrado.")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    total_conf, all_missing = 0, []
    for f in files:
        with open(f, encoding="utf-8", newline="") as fh:
            text = fh.read()
        try:
            new, log, conflicts, missing, n = process(text, MAPPING)
        except Exception as e:
            print(f"\n[ERRO] {f.name}: {e} - ficheiro não alterado")
            continue

        print(f"\n=== {f.name}: {n} alterações ===")
        print("\n".join(log) if log else "  (nada a migrar)")
        if conflicts:
            print("  CONFLITOS:")
            print("\n".join(conflicts))
        total_conf += len(conflicts)
        all_missing += [f"{f.name}: {m}" for m in missing]

        if args.apply and n:
            shutil.copy2(f, f.with_name(f"{f.name}.{stamp}.bak"))
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)

    print("\n" + "=" * 60)
    print(f"Conflitos por resolver: {total_conf}")
    print(f"Componentes na BOM sem {CHECK_FIELD} (depois da migração): {len(all_missing)}")
    for m in all_missing:
        print("  " + m)
    if not args.apply:
        print("\nModo de teste: nada foi gravado. Corre com --apply para aplicar.")
    else:
        print(f"\nGravado. Cópias de segurança: *.kicad_sch.{stamp}.bak")


if __name__ == "__main__":
    main()
