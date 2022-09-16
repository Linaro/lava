from lava_dispatcher.utils.params import substitute_parameters


def test_substitute_parameters():
    params = {"param1": "value1", "param2": "value2", "param3": "param"}

    def get_param(param):
        return params[param] if param in params else f"<not found {param}>"

    assert substitute_parameters("${param1}", get_param) == "value1"
    assert substitute_parameters("$param1", get_param) == "value1"
    assert substitute_parameters("p${param1}", get_param) == "pvalue1"
    assert substitute_parameters("${param1}q", get_param) == "value1q"
    assert substitute_parameters("p${param1}q", get_param) == "pvalue1q"
    assert substitute_parameters("p $param1", get_param) == "p value1"
    assert substitute_parameters("p $param1 q", get_param) == "p value1 q"
    assert substitute_parameters("$param1 ", get_param) == "value1 "
    assert substitute_parameters("p$param1 ", get_param) == "pvalue1 "
    assert substitute_parameters("p$param1", get_param) == "pvalue1"

    assert substitute_parameters("${$param2}", get_param) == "${value2}"
    assert substitute_parameters("$$param2", get_param) == "$value2"
    assert substitute_parameters("p${$param2}", get_param) == "p${value2}"
    assert substitute_parameters("${$param2}q", get_param) == "${value2}q"
    assert substitute_parameters("p${$param2}q", get_param) == "p${value2}q"
    assert substitute_parameters("p $$param2", get_param) == "p $value2"
    assert substitute_parameters("p $$param2 q", get_param) == "p $value2 q"
    assert substitute_parameters("$$param2 ", get_param) == "$value2 "
    assert substitute_parameters("p$$param2 ", get_param) == "p$value2 "
    assert substitute_parameters("p$$param2", get_param) == "p$value2"

    assert substitute_parameters("$param1 $param1", get_param) == "value1 value1"
    assert substitute_parameters("$param1$param1", get_param) == "value1value1"

    assert substitute_parameters(r"\$param1", get_param) == "$param1"
    assert substitute_parameters(r"\${param1}", get_param) == "${param1}"
    assert substitute_parameters(r"\${param1}$param1", get_param) == "${param1}value1"
    assert (
        substitute_parameters(r"$param1.\${param1}.$param1", get_param)
        == "value1.${param1}.value1"
    )

    assert substitute_parameters(r"$.param1", get_param) == "$.param1"
    assert substitute_parameters(r"$\$param1", get_param) == "$$param1"

    assert substitute_parameters("$${param3}1", get_param) == "$param1"

    assert (
        substitute_parameters("$${${${${${param3}3}3}3}3}3", get_param)
        == "$${${${${param3}3}3}3}3"
    )

    def miss_param(_param):
        return None

    assert substitute_parameters(r"\$param1", miss_param) == r"\$param1"
    assert substitute_parameters(r"\${param1}", miss_param) == r"\${param1}"
    assert (
        substitute_parameters(r"\${param1}$param1", miss_param) == r"\${param1}$param1"
    )
    assert (
        substitute_parameters(r"$param1.\${param1}.$param1", miss_param)
        == r"$param1.\${param1}.$param1"
    )

    assert substitute_parameters("${param1}", miss_param) == "${param1}"
    assert substitute_parameters("$param1", miss_param) == "$param1"
    assert substitute_parameters("p${param1}", miss_param) == "p${param1}"
    assert substitute_parameters("${param1}q", miss_param) == "${param1}q"
    assert substitute_parameters("p${param1}q", miss_param) == "p${param1}q"
    assert substitute_parameters("p $param1", miss_param) == "p $param1"
    assert substitute_parameters("p $param1 q", miss_param) == "p $param1 q"
    assert substitute_parameters("$param1 ", miss_param) == "$param1 "
    assert substitute_parameters("p$param1 ", miss_param) == "p$param1 "
    assert substitute_parameters("p$param1", miss_param) == "p$param1"

    assert substitute_parameters("p$", miss_param) == "p$"
    assert substitute_parameters("p${abcdef", miss_param) == "p${abcdef"
    assert substitute_parameters("p$abc", miss_param) == "p$abc"

    assert substitute_parameters("abc$", miss_param) == "abc$"
    assert substitute_parameters("abc\\$", miss_param) == "abc\\$"

    assert substitute_parameters("abc\\", miss_param) == "abc\\"
