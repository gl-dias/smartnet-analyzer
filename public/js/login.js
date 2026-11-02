// Envia as credenciais e abre a aplicação. O cookie de sessão é definido pelo servidor.

const formulario = document.querySelector("#form-login");
const areaErro = document.querySelector("#erro-login");
const botaoEntrar = document.querySelector("#botao-entrar");

function mostrarErro(mensagem) {
  areaErro.textContent = mensagem;
  areaErro.hidden = false;
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  areaErro.hidden = true;
  botaoEntrar.disabled = true;
  try {
    const resposta = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario: document.querySelector("#usuario").value,
        senha: document.querySelector("#senha").value,
      }),
    });
    if (resposta.ok) {
      window.location.href = "/";
      return;
    }
    const dados = await resposta.json().catch(() => ({}));
    mostrarErro(dados.erro || "Não foi possível entrar. Tente novamente.");
    document.querySelector("#senha").value = "";
    document.querySelector("#senha").focus();
  } catch {
    mostrarErro("Não foi possível falar com o servidor. Verifique a conexão.");
  } finally {
    botaoEntrar.disabled = false;
  }
});
