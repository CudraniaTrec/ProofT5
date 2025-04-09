import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class RemoveParenthesis{
  public static String removeParenthesis(List<String> items){
    String result = "";
    for (String item : items){
      if (item.contains("(")){
        int pos = item.indexOf("(");
        if (pos > 0){
          String subString = item.substring(0, pos);
          String[] splitString = subString.split("\\s+");
          result = result.concat(splitString[0]);
        }
      }
    }
    return result;
  }
}

class Main {
    public static boolean compare(Object obj1, Object obj2) {
        if (obj1 == null && obj2 == null){
            return true;
        } else if (obj1 == null || obj2 == null){
            return false;
        } else {
            return obj1.equals(obj2);
        }
    }
    
    public static void main(String[] args) throws Exception {
        List<String> arg00 = Arrays.asList("python (chrome)");
        String x0 = RemoveParenthesis.removeParenthesis(Arrays.asList("python (chrome)"));
        String v0 = "python";
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        List<String> arg10 = Arrays.asList("string(.abc)");
        String x1 = RemoveParenthesis.removeParenthesis(Arrays.asList("string(.abc)"));
        String v1 = "string";
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        List<String> arg20 = Arrays.asList("alpha(num)");
        String x2 = RemoveParenthesis.removeParenthesis(Arrays.asList("alpha(num)"));
        String v2 = "alpha";
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
