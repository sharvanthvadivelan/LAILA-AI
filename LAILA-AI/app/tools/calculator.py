import ast, math, operator

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def calculate(expression):
    if len(expression) > 200:
        raise ValueError("Expression too long.")
    try:
        node = ast.parse(
            expression.replace("×", "*").replace("÷", "/").replace("^", "**"),
            mode="eval",
        )
    except SyntaxError as exc:
        raise ValueError(
            "Enter a numeric expression such as 12 + 8. Variables and code are not supported by the calculator."
        ) from exc
    if sum(1 for _ in ast.walk(node)) > 80:
        raise ValueError("Expression too complex.")

    def solve(n):
        if isinstance(n, ast.Expression):
            return solve(n.body)
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            value = n.value
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            value = solve(n.operand) * (1 if isinstance(n.op, ast.UAdd) else -1)
        elif isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = solve(n.left), solve(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e12):
                raise ValueError("Exponent too large.")
            value = OPS[type(n.op)](a, b)
        else:
            raise ValueError("Only arithmetic numbers and operators are allowed.")
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError("Result outside supported range.")
        return value

    return {"expression": expression, "result": solve(node)}
