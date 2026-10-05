const { LanguageClient, TransportKind } = require('vscode-languageclient');
const path = require('path');
const vscode = require('vscode');

let client;

function activate(context) {
    // Caminho para o script LSP dentro da pasta da extensão
    let serverModule = context.asAbsolutePath(path.join('lumina_lsp.py'));
    
    // Pega o caminho da pasta do workspace aberto no VS Code
    // para que o Python consiga encontrar a pasta 'lumina/' do compilador
    let workspacePath = vscode.workspace.workspaceFolders 
        ? vscode.workspace.workspaceFolders[0].uri.fsPath 
        : process.cwd();

    let serverOptions = {
        run: { 
            command: 'python3', 
            args: [serverModule],
            options: { 
                env: { 
                    ...process.env, 
                    PYTHONPATH: workspacePath 
                } 
            } 
        },
        debug: { 
            command: 'python3', 
            args: [serverModule],
            options: { 
                env: { 
                    ...process.env, 
                    PYTHONPATH: workspacePath 
                } 
            } 
        }
    };
    
    let clientOptions = {
        documentSelector: [{ scheme: 'file', language: 'lumina' }],
    };
    
    client = new LanguageClient(
        'luminaLanguageServer',
        'Lumina Language Server',
        serverOptions,
        clientOptions
    );
    
    client.start();
}

function deactivate() {
    if (!client) {
        return undefined;
    }
    return client.stop();
}

module.exports = {
    activate,
    deactivate
};