class NodeVisitor:
    """
    Classe base para todos os visitantes (Analyzers, Codegens, etc).
    Despacha a chamada para o método correto baseado no tipo do nó.
    """
    def visit(self, node):
        if node is None:
            return None

        method_name = f'visit_{type(node).__name__}'
        visitor_method = getattr(self, method_name, self.generic_visit)
        return visitor_method(node)

    def generic_visit(self, node):
        """Método padrão caso o Visitor não implemente a visita para um nó específico"""
        raise NotImplementedError(
            f"{self.__class__.__name__} não implementou visita para {type(node).__name__}"
        )