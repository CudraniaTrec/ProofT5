import java.io.*;
import java.math.*;
import java.util.*;
import java.lang.*;
class ReplaceSpecialchar{
  public static String replaceSpecialchar(String text){
    text = text.replaceAll(" ", ":");
    text = text.replaceAll("\\.", ":");
    text = text.replaceAll(",", ":");
    return text;
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
        String arg00 = "Python language, Programming language.";
        String x0 = ReplaceSpecialchar.replaceSpecialchar("Python language, Programming language.");
        String v0 = "Python:language::Programming:language:";
        if (!(compare(x0, v0))) {
            throw new java.lang.Exception("Exception -- test case 0 did not pass. x0 = " + x0);
        }

        String arg10 = "a b c,d e f";
        String x1 = ReplaceSpecialchar.replaceSpecialchar("a b c,d e f");
        String v1 = "a:b:c:d:e:f";
        if (!(compare(x1, v1))) {
            throw new java.lang.Exception("Exception -- test case 1 did not pass. x1 = " + x1);
        }

        String arg20 = "ram reshma,ram rahim";
        String x2 = ReplaceSpecialchar.replaceSpecialchar("ram reshma,ram rahim");
        String v2 = "ram:reshma:ram:rahim";
        if (!(compare(x2, v2))) {
            throw new java.lang.Exception("Exception -- test case 2 did not pass. x2 = " + x2);
        }


}
}
